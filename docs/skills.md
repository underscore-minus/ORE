# ORE Skill Design Decisions (v0.7.1)

Locked design decisions for v0.8 (Skill / Instruction Activation). These resolve all open architectural questions identified during the v0.7 review. Implementation must follow these decisions exactly — they are not suggestions.

For philosophical foundations, see [foundation.md](foundation.md). For mechanical invariants, see [invariants.md](invariants.md).

---

## 1. Injection Order

```
[system] + [skill_messages...] + [tool_results...] + session.messages + [user]
```

Skills before tool results. Skills set a behavioral frame (how the model should act); tool results provide factual context (what the model should know). Both are turn-scoped — never stored in the session.

---

## 2. Skill Message Role

`role="system"` with a `[Skill:name]` prefix.

Skills extend the system prompt, not the conversation. Using `role="user"` would misrepresent their authority to the model. The `[Skill:name]` prefix is applied by the CLI layer, not by `ORE.execute()` — the engine receives plain instruction strings and stays generic.

---

## 3. `ORE.execute()` API

Add one new explicit parameter:

```python
def execute(self, prompt, session=None, tool_results=None, skill_context=None)
```

`skill_context: Optional[List[str]]` — a list of instruction strings, one per activated skill. Skills are not `ToolResult` objects and must not be treated as such. When `skill_context` is `None`, behavior is identical to v0.7.

---

## 4. Simultaneous Tool + Skill

Permitted. Injection order follows the rule in Decision 1.

The routing layer (`--route`) selects one target per turn — multi-activation via routing is a post-v0.8 concern. However, `--tool` and `--skill` can coexist on the same invocation: `--skill` provides behavioral context, `--tool` provides factual context, and both are injected into the same turn.

---

## 5. Level 3 Resources

Passive injection only in v0.8. Resources are file contents injected into context when referenced by skill instructions. Executable scripts are explicitly deferred — not forbidden, just out of scope for the current version.

This constraint is also recorded in [foundation.md](foundation.md) under "What ORE Is Not (Yet)."

---

## 6. Routing Decisions in REPL

Intentionally ephemeral in REPL modes. Routing decisions are printed to stderr and discarded. Structured routing logs belong to a future platform layer, not the CLI.

This is a conscious design choice, not a gap. Document it as such.
