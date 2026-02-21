"""Surface/invariant tests for frozen public API (interface lock v1.0)."""

from __future__ import annotations

import pytest

# Minimum set of names that must be in ore.__all__ (additions allowed, removals not).
ORE_ALL_MINIMUM = frozenset(
    {
        "__version__",
        "ARTIFACT_VERSION",
        "ExecutionArtifact",
        "run",
        "ORE",
        "Reasoner",
        "AyaReasoner",
        "Message",
        "Response",
        "RoutingDecision",
        "RoutingTarget",
        "Router",
        "RuleRouter",
        "TEST_ROUTING_TARGET",
        "build_targets_from_registry",
        "SkillMetadata",
        "build_skill_registry",
        "build_targets_from_skill_registry",
        "load_skill_metadata",
        "load_skill_instructions",
        "load_skill_resource",
        "Session",
        "SessionStore",
        "FileSessionStore",
        "fetch_models",
        "default_model",
        "Tool",
        "TOOL_REGISTRY",
        "Gate",
        "GateError",
        "Permission",
        "ToolResult",
    }
)


@pytest.mark.invariant
def test_ore_all_contains_minimum_exports():
    """Invariant: ore.__all__ contains at least the minimum public API set."""
    import ore

    actual = set(ore.__all__)
    assert (
        ORE_ALL_MINIMUM <= actual
    ), f"Missing from ore.__all__: {ORE_ALL_MINIMUM - actual}"


@pytest.mark.invariant
def test_ore_all_exports_are_importable():
    """Invariant: every name in __all__ is importable from ore."""
    import ore

    for name in ore.__all__:
        assert hasattr(ore, name), f"ore.{name} missing (in __all__ but not on module)"
