"""
Routing layer (v0.7): intent detection without an extra LLM call.
Router selects a target (tool or skill) from user prompt via rules/keywords.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, TYPE_CHECKING

from .types import RoutingDecision, RoutingTarget

if TYPE_CHECKING:
    from .tools import Tool


# Default threshold for RuleRouter. Below this, we return fallback.
# Deterministic: same prompt + targets always yields same decision.
# Tie-break: among equal confidence, sort by target name (asc) and pick first.
DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# Test-only routing target: high-confidence hint for deterministic tests.
# name must match a key in TOOL_REGISTRY (e.g. "echo"). Use in tests by
# passing [TEST_ROUTING_TARGET] or merging with build_targets_from_registry().
TEST_ROUTING_TARGET = RoutingTarget(
    name="echo",
    target_type="tool",
    description="Echo (test hint).",
    hints=["repeat this line"],
)


def build_targets_from_registry(registry: Dict[str, "Tool"]) -> List[RoutingTarget]:
    """
    Build a list of RoutingTarget from TOOL_REGISTRY (or any name -> Tool dict).
    Does not mutate the registry. Each target gets hints from tool.routing_hints().
    """
    targets: List[RoutingTarget] = []
    for name, tool in sorted(registry.items()):
        hints = list(tool.routing_hints())
        targets.append(
            RoutingTarget(
                name=name,
                target_type="tool",
                description=tool.description,
                hints=hints,
            )
        )
    return targets


class Router(ABC):
    """Abstract router: prompt + targets -> RoutingDecision. No LLM."""

    @abstractmethod
    def route(self, prompt: str, targets: List[RoutingTarget]) -> RoutingDecision:
        """
        Select a target (or fallback) from the prompt. Must not mutate targets.
        """
        ...


class RuleRouter(Router):
    """
    Rule-based router: keyword/phrase matching against target hints.

    Confidence is computed deterministically:
    - For each target, score = (longest matching hint length) / (max possible hint length in list).
    - Max possible is the length of the longest hint across all targets (or 1 if none).
    - Score is then capped and used as confidence. Tie-break: lexicographically
      first target name (asc) among those with the same confidence.
    """

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        """
        confidence_threshold: minimum confidence (0.0 to 1.0) to select a target.
        Below this, returns fallback. Default 0.5. Documented and deterministic.
        """
        self.confidence_threshold = confidence_threshold

    def route(self, prompt: str, targets: List[RoutingTarget]) -> RoutingDecision:
        """
        Match prompt against each target's hints (case-insensitive).
        Does not mutate targets; only reads from the list.
        """
        if not targets:
            return RoutingDecision(
                target=None,
                target_type="fallback",
                confidence=0.0,
                args={},
                reasoning="No targets available.",
            )
        prompt_lower = prompt.strip().lower()
        if not prompt_lower:
            return RoutingDecision(
                target=None,
                target_type="fallback",
                confidence=0.0,
                args={},
                reasoning="Empty prompt.",
            )

        # Compute best match length per target (read-only over targets)
        max_hint_len = 1
        for t in targets:
            for h in t.hints:
                if len(h) > max_hint_len:
                    max_hint_len = len(h)

        best: List[tuple[float, str, int]] = []  # (confidence, name, match_len)
        for t in targets:
            best_len = 0
            for h in t.hints:
                if h.lower() in prompt_lower and len(h) > best_len:
                    best_len = len(h)
            if best_len > 0:
                confidence = min(1.0, best_len / max_hint_len)
                best.append((confidence, t.name, best_len))

        if not best:
            return RoutingDecision(
                target=None,
                target_type="fallback",
                confidence=0.0,
                args={},
                reasoning="No hint matched the prompt.",
            )

        # Deterministic tie-break: sort by confidence desc, then name asc
        best.sort(key=lambda x: (-x[0], x[1]))
        top_confidence, top_name, top_len = best[0]
        if top_confidence < self.confidence_threshold:
            return RoutingDecision(
                target=None,
                target_type="fallback",
                confidence=top_confidence,
                args={},
                reasoning=f"Best match '{top_name}' below threshold "
                f"({top_confidence:.2f} < {self.confidence_threshold}).",
            )

        # Find the target to get reasoning (by name)
        chosen = next(t for t in targets if t.name == top_name)
        matched_hint = next(
            h for h in chosen.hints if h.lower() in prompt_lower and len(h) == top_len
        )
        return RoutingDecision(
            target=top_name,
            target_type=chosen.target_type,
            confidence=top_confidence,
            args={},  # CLI will call tool.extract_args(prompt) for the chosen tool
            reasoning=f"Matched hint \"{matched_hint}\" for {chosen.target_type} '{top_name}'.",
        )
