"""Tests for ore/router.py — routing layer (v0.7)."""

from __future__ import annotations

import copy

import pytest

from ore.router import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    RuleRouter,
    TEST_ROUTING_TARGET,
    build_targets_from_registry,
)
from ore.tools import TOOL_REGISTRY
from ore.types import RoutingTarget


class TestBuildTargetsFromRegistry:
    def test_builds_list_from_registry(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        assert len(targets) == 2
        names = {t.name for t in targets}
        assert "echo" in names
        assert "read-file" in names

    def test_each_target_has_hints_from_tool(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        echo_target = next(t for t in targets if t.name == "echo")
        assert "echo" in echo_target.hints
        assert echo_target.target_type == "tool"
        read_target = next(t for t in targets if t.name == "read-file")
        assert "read file" in read_target.hints


class TestRuleRouter:
    def test_returns_fallback_for_empty_prompt(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        router = RuleRouter()
        decision = router.route("", targets)
        assert decision.target is None
        assert decision.target_type == "fallback"
        assert decision.confidence == 0.0

    def test_returns_fallback_for_no_match(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        router = RuleRouter()
        decision = router.route("what is the weather today", targets)
        assert decision.target is None
        assert decision.target_type == "fallback"

    def test_matches_echo_prompt(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        # Use lower threshold so short hint "echo" (vs long "read the file") passes
        router = RuleRouter(confidence_threshold=0.2)
        decision = router.route("please echo hello world", targets)
        assert decision.target == "echo"
        assert decision.target_type == "tool"
        assert decision.confidence >= 0.2
        assert "echo" in decision.reasoning.lower()

    def test_matches_read_file_prompt(self):
        targets = build_targets_from_registry(TOOL_REGISTRY)
        router = RuleRouter()
        decision = router.route("read the file at /tmp/foo.txt", targets)
        assert decision.target == "read-file"
        assert decision.target_type == "tool"
        assert decision.confidence >= DEFAULT_CONFIDENCE_THRESHOLD

    def test_test_routing_target_exact_hint(self):
        """TEST_ROUTING_TARGET: prompt 'repeat this line' routes to echo with high confidence."""
        router = RuleRouter()
        decision = router.route("repeat this line", [TEST_ROUTING_TARGET])
        assert decision.target == "echo"
        assert decision.target_type == "tool"
        assert decision.confidence >= DEFAULT_CONFIDENCE_THRESHOLD
        assert "repeat this line" in decision.reasoning

    def test_longer_hint_higher_confidence(self):
        # "read the file" is longer than "read file" — should win when both match
        targets = [
            RoutingTarget("a", "tool", "desc", ["x"]),
            RoutingTarget("b", "tool", "desc", ["x y"]),
        ]
        router = RuleRouter(confidence_threshold=0.0)
        decision = router.route("please x y", targets)
        assert decision.target == "b"
        assert decision.confidence > 0.0

    def test_below_threshold_returns_fallback(self):
        # Long hint elsewhere makes "z" match score low (1/20 < 0.99)
        targets = [
            RoutingTarget("short", "tool", "desc", ["z"]),
            RoutingTarget("long", "tool", "desc", ["a very long hint phrase here"]),
        ]
        router = RuleRouter(confidence_threshold=0.99)
        decision = router.route("z", targets)
        assert decision.target is None
        assert decision.target_type == "fallback"
        assert "below threshold" in decision.reasoning.lower()

    def test_deterministic_tie_break_by_name(self):
        targets = [
            RoutingTarget("echo", "tool", "desc", ["hi"]),
            RoutingTarget("alpha", "tool", "desc", ["hi"]),
        ]
        router = RuleRouter(confidence_threshold=0.0)
        decision = router.route("hi", targets)
        # Same confidence; first by name asc is "alpha"
        assert decision.target == "alpha"

    def test_empty_targets_returns_fallback(self):
        router = RuleRouter()
        decision = router.route("anything", [])
        assert decision.target is None
        assert "No targets" in decision.reasoning

    def test_confidence_documentation(self):
        """Threshold is documented and used deterministically."""
        targets = build_targets_from_registry(TOOL_REGISTRY)
        router = RuleRouter(confidence_threshold=0.5)
        d1 = router.route("echo something", targets)
        d2 = router.route("echo something", targets)
        assert d1.target == d2.target
        assert d1.confidence == d2.confidence


class TestRuleRouterWithSkillTargets:
    """v0.8: verify RuleRouter works with target_type='skill'."""

    def test_route_selects_skill_target(self):
        targets = [
            RoutingTarget("my-skill", "skill", "A test skill", ["activate skill"]),
            RoutingTarget("echo", "tool", "Echo tool", ["echo"]),
        ]
        router = RuleRouter(confidence_threshold=0.0)
        decision = router.route("please activate skill now", targets)
        assert decision.target == "my-skill"
        assert decision.target_type == "skill"

    def test_mixed_tool_and_skill_targets(self):
        targets = [
            RoutingTarget("my-skill", "skill", "A skill", ["summarize"]),
            RoutingTarget("echo", "tool", "Echo", ["echo"]),
        ]
        router = RuleRouter(confidence_threshold=0.0)
        # "echo" should match the tool
        decision = router.route("echo hello", targets)
        assert decision.target == "echo"
        assert decision.target_type == "tool"
        # "summarize" should match the skill
        decision = router.route("summarize the document", targets)
        assert decision.target == "my-skill"
        assert decision.target_type == "skill"


@pytest.mark.invariant
def test_route_does_not_mutate_targets_list():
    """Invariant: routing must not mutate the targets list or its items."""
    targets = build_targets_from_registry(TOOL_REGISTRY)
    targets_copy = copy.deepcopy(targets)
    router = RuleRouter()
    router.route("echo hello", targets)
    assert len(targets) == len(targets_copy)
    for t, tc in zip(targets, targets_copy):
        assert t.name == tc.name
        assert t.hints == tc.hints
        assert t.target_type == tc.target_type
        assert t.description == tc.description


@pytest.mark.invariant
def test_route_does_not_mutate_skill_targets():
    """Invariant: routing must not mutate skill targets either."""
    targets = [
        RoutingTarget("my-skill", "skill", "A skill", ["do the thing"]),
    ]
    targets_copy = copy.deepcopy(targets)
    router = RuleRouter(confidence_threshold=0.0)
    router.route("do the thing", targets)
    assert len(targets) == len(targets_copy)
    for t, tc in zip(targets, targets_copy):
        assert t.name == tc.name
        assert t.hints == tc.hints
        assert t.target_type == tc.target_type
