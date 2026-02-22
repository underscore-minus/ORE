# ORE Interface Lock (v1.1)

This document is the **frozen contract** for ORE consumers. It enumerates CLI flags, exit codes, schemas, and public API surfaces that must not be broken. Additions are allowed; removals or incompatible changes are not. For rationale and invariants, see [foundation.md](foundation.md) and [invariants.md](invariants.md).

---

## 1. CLI Flags

Source: `ore/cli.py` — `_build_parser()`.

| Flag | Short | Type | Default | Metavar |
|------|-------|------|---------|---------|
| `prompt` | — | str, positional, optional | `None` | — |
| `--model` | — | str | `None` | `NAME` |
| `--list-models` | — | store_true | `False` | — |
| `--interactive` | `-i` | store_true | `False` | — |
| `--conversational` | `-c` | store_true | `False` | — |
| `--save-session` | — | str | `None` | `NAME` |
| `--resume-session` | — | str | `None` | `NAME` |
| `--stream` | `-s` | store_true | `False` | — |
| `--verbose` | `-v` | store_true | `False` | — |
| `--json` | `-j` | store_true | `False` | — |
| `--tool` | — | str | `None` | `NAME` |
| `--tool-arg` | — | append | `[]` | `KEY=VALUE` |
| `--list-tools` | — | store_true | `False` | — |
| `--grant` | — | append | `[]` | `PERM` |
| `--route` | — | store_true | `False` | — |
| `--route-threshold` | — | float | `0.5` | `FLOAT` |
| `--skill` | — | str | `None` | `NAME` |
| `--list-skills` | — | store_true | `False` | — |
| `--artifact-out` | — | str, nargs="?" | `None` (const=`"-"`) | `PATH` |
| `--artifact-in` | — | str | `None` | `PATH` |
| `--system` | — | str | `""` | `PROMPT` |

**Total: 21 flags (1 positional + 20 named).** New flags may be added; existing flags must not be removed or changed in type/default.

---

## 2. Mutual Exclusions

Invalid flag combinations cause `parser.error` and **exit code 2**.

| Combination | Error behavior |
|-------------|----------------|
| `--route` + `--tool` | exit 2 |
| `--interactive` + `--conversational` | exit 2 |
| `--interactive` + `--save-session` | exit 2 |
| `--interactive` + `--resume-session` | exit 2 |
| `--json` + `--stream` | exit 2 |
| `--json` + REPL modes (`-i`, `-c`, `--save-session`, `--resume-session`) | exit 2 |
| `--artifact-in` + `prompt` (positional) | exit 2 |
| `--artifact-in` + REPL modes | exit 2 |
| `--artifact-in` + `--tool` / `--route` / `--skill` | exit 2 |
| `--artifact-out` + `--stream` | exit 2 |
| `--artifact-out` + REPL modes | exit 2 |
| `--artifact-out -` + `--json` | exit 2 |

---

## 3. Exit Codes

| Code | Condition |
|------|------------|
| **0** | Success: `--list-models`, `--list-tools`, or `--list-skills` completed successfully. |
| **1** | Application error: no Ollama models; unknown tool/skill; `GateError` (tool denied); unknown `--grant` value; `--resume-session` file not found; `--artifact-in` file not found / read error / invalid JSON / invalid artifact schema. |
| **2** | Usage error: `parser.error` (mutual exclusion, missing prompt, or invalid combination). |

---

## 4. `--json` Output Schema

When `--json` is used, stdout is a single JSON object.

**Base keys (always present):** `id`, `model_id`, `content`, `timestamp`, `metadata`.

**When `--route` is used and a routing decision exists,** the object also has a `routing` key with: `target`, `target_type`, `confidence`, `args`, `reasoning`, `id`, `timestamp`.

Without `--route`, the payload has exactly the 5 base keys. New keys may be added in the future; consumers must tolerate unknown keys.

---

## 5. Execution Artifact Schema

Version constant: `ARTIFACT_VERSION = "ore.exec.v1"` in `ore/types.py`.

Required top-level keys: `artifact_version`, `execution_id`, `timestamp`, `input`, `output`, `continuation`.

- `input`: `prompt`, `model_id`, `mode` (required); `routing`, `tools`, `skills` (optional).
- `output`: `id`, `content`, `model_id`, `timestamp`, `metadata` (all required).
- `continuation`: `requested` (required), `reason` (optional).

See [artifact-schema.md](artifact-schema.md) for full details. Forward compatibility: unknown top-level keys are tolerated on parse.

---

## 6. `ORE` Constructor and Execute Signatures

**`ORE.__init__(self, reasoner: Reasoner, system_prompt: str = "")`**

- `reasoner`: the `Reasoner` implementation to use.
- `system_prompt`: optional system prompt string; default `""`. Consumers (CLI, scripts) provide the persona or instructions; the engine does not load any prompt file.

---

**`ORE.execute()` / `ORE.execute_stream()`**

```python
def execute(
    self,
    user_prompt: str,
    session: Optional[Session] = None,
    tool_results: Optional[List[ToolResult]] = None,
    skill_context: Optional[List[str]] = None,
) -> Response

def execute_stream(
    self,
    user_prompt: str,
    session: Optional[Session] = None,
    tool_results: Optional[List[ToolResult]] = None,
    skill_context: Optional[List[str]] = None,
) -> Generator[str, None, Response]
```

Message list order: `[system] + [skill_context as role="system"] + [tool_results as role="user"] + session.messages + [user]`.

---

## 7. Data Contracts (`ore/types.py`)

| Dataclass | Fields (name: type) |
|-----------|----------------------|
| `Message` | `role`, `content`, `id`, `timestamp` |
| `Response` | `content`, `model_id`, `id`, `timestamp`, `metadata` |
| `Session` | `messages`, `id`, `created_at` |
| `ToolResult` | `tool_name`, `output`, `status`, `id`, `timestamp`, `metadata` |
| `SkillMetadata` | `name`, `description`, `hints`, `path` |
| `RoutingTarget` | `name`, `target_type`, `description`, `hints` |
| `RoutingDecision` | `target`, `target_type`, `confidence`, `args`, `reasoning`, `id`, `timestamp` |
| `ExecutionArtifactInput` | `prompt`, `model_id`, `mode`, `routing`, `tools`, `skills` |
| `ExecutionArtifactOutput` | `id`, `content`, `model_id`, `timestamp`, `metadata` |
| `ExecutionArtifactContinuation` | `requested`, `reason` |
| `ExecutionArtifact` | `artifact_version`, `execution_id`, `timestamp`, `input`, `output`, `continuation` |

Field names and presence are frozen; new optional fields may be added.

---

## 8. Session File Format

Location: `~/.ore/sessions/<name>.json`.

Top-level keys: `id`, `created_at`, `messages`. Each message object: `role`, `content`, `id`, `timestamp`.

---

## 9. Skill Format

Location: `~/.ore/skills/<dir-name>/SKILL.md`. YAML frontmatter required: `name`, `description`; optional: `hints`. Body after `---` is Level 2 instructions. Resources: `<skill-dir>/resources/`.

---

## 10. Permission Enum Values

`ore/gate.py`: `Permission` enum.

| Name | Value |
|------|-------|
| `FILESYSTEM_READ` | `"filesystem-read"` |
| `FILESYSTEM_WRITE` | `"filesystem-write"` |
| `SHELL` | `"shell"` |
| `NETWORK` | `"network"` |

---

## 11. Tool ABC / Reasoner ABC

**Tool** (`ore/tools.py`): abstract `name`, `description`, `required_permissions`, `run(args) -> ToolResult`; optional overrides `routing_hints()`, `extract_args(prompt)`.

**Reasoner** (`ore/reasoner.py`): abstract `reason(messages) -> Response`; optional override `stream_reason(messages) -> Generator[str, None, Response]`.

---

## 12. `ore/__init__.py` Exports

`__all__` defines the minimum public API. All listed names must remain importable as `from ore import <name>`. New names may be added; removals are breaking.

(Current minimum set is asserted by invariant tests; see `tests/test_surface.py`.)

---

## 13. Router / Gate Constants

- `DEFAULT_CONFIDENCE_THRESHOLD = 0.5` (`ore/router.py`).
- Gate: default-deny; `Gate.check(tool)` raises `GateError` if permissions missing; `Gate.run(tool, args)` runs only after check. Denied tools never execute.
