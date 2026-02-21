# ORE v1.0 Upgrade Plan

This document is the execution plan for v0.9.1 (Interface Lock) and v1.0 (The Mainframe). It was produced by auditing the actual code, not the documentation. It is structured so that any competent developer can execute it mechanically.

---

## Phase 1 — Surface Audit (Inventory)

Every contract a consumer could depend on, enumerated from source.

---

### 1.1 CLI Flags

Source: `ore/cli.py` lines 254–392.

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

**Total: 20 flags (1 positional + 19 named).**

### 1.2 Mutual Exclusions

Source: `ore/cli.py` lines 395–437, 496–501.

| Combination | Error behavior |
|-------------|---------------|
| `--route` + `--tool` | `parser.error` (exit 2) |
| `--interactive` + `--conversational` | `parser.error` (exit 2) |
| `--interactive` + `--save-session` | `parser.error` (exit 2) |
| `--interactive` + `--resume-session` | `parser.error` (exit 2) |
| `--json` + `--stream` | `parser.error` (exit 2) |
| `--json` + REPL modes (`-i`, `-c`, `--save-session`, `--resume-session`) | `parser.error` (exit 2) |
| `--artifact-in` + `prompt` (positional) | `parser.error` (exit 2) |
| `--artifact-in` + REPL modes | `parser.error` (exit 2) |
| `--artifact-in` + `--tool` / `--route` / `--skill` | `parser.error` (exit 2) |
| `--artifact-out` + `--stream` | `parser.error` (exit 2) |
| `--artifact-out` + REPL modes | `parser.error` (exit 2) |
| `--artifact-out -` + `--json` | `parser.error` (exit 2) |

### 1.3 Exit Codes

Source: `ore/cli.py` — all `sys.exit()` calls.

| Code | Condition | Source line(s) |
|------|-----------|----------------|
| 0 | `--list-models` success | 447 |
| 0 | `--list-tools` success | 462 |
| 0 | `--list-skills` success (with or without skills) | 470, 478 |
| 1 | No Ollama models found (startup) | 443, 526 |
| 1 | Unknown tool name | 103 |
| 1 | `GateError` (tool denied) | 111, 190 |
| 1 | Unknown skill name | 126 |
| 1 | Unknown permission value in `--grant` | 488 |
| 1 | `--resume-session` file not found | 581 |
| 1 | `--artifact-in` file not found | 57 |
| 1 | `--artifact-in` file read error | 60 |
| 1 | `--artifact-in` invalid JSON | 65 |
| 1 | `--artifact-in` invalid artifact schema | 70 |
| 2 | `parser.error` (mutual exclusion / missing prompt) | argparse default |

### 1.4 `--json` Output Schema

Source: `ore/cli.py` `_print_json_response()` lines 193–215.

```json
{
  "id": "string (uuid)",
  "model_id": "string",
  "content": "string",
  "timestamp": "float (unix)",
  "metadata": "dict",
  "routing": {
    "target": "string | null",
    "target_type": "string",
    "confidence": "float",
    "args": "dict",
    "reasoning": "string",
    "id": "string (uuid)",
    "timestamp": "float (unix)"
  }
}
```

`routing` key is present only when `--route` is used and a routing decision exists. Without `--route`, the payload has exactly 5 keys: `id`, `model_id`, `content`, `timestamp`, `metadata`.

### 1.5 Execution Artifact Schema

Source: `ore/types.py` `ExecutionArtifact.to_dict()` lines 263–288. Documented in `docs/artifact-schema.md`.

| Field | Type | Required |
|-------|------|----------|
| `artifact_version` | `"ore.exec.v1"` | yes |
| `execution_id` | string | yes |
| `timestamp` | float | yes |
| `input.prompt` | string | yes |
| `input.model_id` | string | yes |
| `input.mode` | string | yes (`"single_turn"`) |
| `input.routing` | dict \| null | no |
| `input.tools` | list[str] \| null | no |
| `input.skills` | list[str] \| null | no |
| `output.id` | string | yes |
| `output.content` | string | yes |
| `output.model_id` | string | yes |
| `output.timestamp` | float | yes |
| `output.metadata` | dict | yes |
| `continuation.requested` | bool | yes |
| `continuation.reason` | string \| null | no |

Constant: `ARTIFACT_VERSION = "ore.exec.v1"` in `ore/types.py` line 144.

### 1.6 `ORE.execute()` / `ORE.execute_stream()` Signatures

Source: `ore/core.py` lines 37–120.

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

Message list construction order: `[system] + [skill_context as role="system"] + [tool_results as role="user"] + session.messages + [user]`.

### 1.7 Data Contracts (`ore/types.py`)

| Dataclass | Fields (name: type) |
|-----------|---------------------|
| `Message` | `role: str`, `content: str`, `id: str` (auto uuid), `timestamp: float` (auto time) |
| `Response` | `content: str`, `model_id: str`, `id: str` (auto uuid), `timestamp: float` (auto time), `metadata: Dict[str, Any]` (default `{}`) |
| `Session` | `messages: List[Message]` (default `[]`), `id: str` (auto uuid), `created_at: float` (auto time) |
| `ToolResult` | `tool_name: str`, `output: str`, `status: str`, `id: str` (auto uuid), `timestamp: float` (auto time), `metadata: Dict[str, Any]` (default `{}`) |
| `SkillMetadata` | `name: str`, `description: str`, `hints: List[str]`, `path: Path` |
| `RoutingTarget` | `name: str`, `target_type: str`, `description: str`, `hints: List[str]` |
| `RoutingDecision` | `target: Optional[str]`, `target_type: str`, `confidence: float`, `args: Dict[str, str]`, `reasoning: str`, `id: str` (auto uuid), `timestamp: float` (auto time) |
| `ExecutionArtifactInput` | `prompt: str`, `model_id: str`, `mode: str`, `routing: Optional[Dict[str, Any]]`, `tools: Optional[List[str]]`, `skills: Optional[List[str]]` |
| `ExecutionArtifactOutput` | `id: str`, `content: str`, `model_id: str`, `timestamp: float`, `metadata: Dict[str, Any]` |
| `ExecutionArtifactContinuation` | `requested: bool` (default `False`), `reason: Optional[str]` (default `None`) |
| `ExecutionArtifact` | `artifact_version: str`, `execution_id: str`, `timestamp: float`, `input: ExecutionArtifactInput`, `output: ExecutionArtifactOutput`, `continuation: ExecutionArtifactContinuation` |

### 1.8 Session File Format

Source: `ore/store.py` `_session_to_dict()` / `_dict_to_session()`.
Location: `~/.ore/sessions/<name>.json`.

```json
{
  "id": "uuid-string",
  "created_at": 1234567890.123,
  "messages": [
    { "role": "user", "content": "...", "id": "uuid", "timestamp": 1234567890.123 },
    { "role": "assistant", "content": "...", "id": "uuid", "timestamp": 1234567890.123 }
  ]
}
```

### 1.9 Skill Format

Source: `ore/skills.py`.
Location: `~/.ore/skills/<dir-name>/SKILL.md` (+ optional `resources/`).

YAML frontmatter required keys: `name` (str), `description` (str).
YAML frontmatter optional keys: `hints` (list of str).
Body: everything after closing `---` (Level 2 instructions).
Resources: files in `<skill-dir>/resources/` (Level 3, loaded on demand).
Constants: `DEFAULT_SKILLS_ROOT = ~/.ore/skills/`, `SKILL_FILENAME = "SKILL.md"`.

### 1.10 Permission Enum Values

Source: `ore/gate.py` lines 18–24.

| Name | Value |
|------|-------|
| `FILESYSTEM_READ` | `"filesystem-read"` |
| `FILESYSTEM_WRITE` | `"filesystem-write"` |
| `SHELL` | `"shell"` |
| `NETWORK` | `"network"` |

### 1.11 Tool ABC (Extension Interface)

Source: `ore/tools.py` lines 18–53.

A tool implementation must provide:

| Member | Kind | Signature |
|--------|------|-----------|
| `name` | abstract property | `-> str` |
| `description` | abstract property | `-> str` |
| `required_permissions` | abstract property | `-> frozenset[Permission]` |
| `run` | abstract method | `(args: Dict[str, str]) -> ToolResult` |
| `routing_hints` | optional override | `() -> List[str]` (default `[]`) |
| `extract_args` | optional override | `(prompt: str) -> Dict[str, str]` (default `{}`) |

### 1.12 Reasoner ABC (Backend Interface)

Source: `ore/reasoner.py` lines 13–25.

A reasoner implementation must provide:

| Member | Kind | Signature |
|--------|------|-----------|
| `reason` | abstract method | `(messages: List[Message]) -> Response` |
| `stream_reason` | optional override | `(messages: List[Message]) -> Generator[str, None, Response]` (default: yields full content via `reason()`) |

### 1.13 Built-in Tools and Registry

Source: `ore/tools.py` lines 185–188.

| Registry key | Class | Permissions |
|--------------|-------|-------------|
| `"echo"` | `EchoTool` | none |
| `"read-file"` | `ReadFileTool` | `filesystem-read` |

`TOOL_REGISTRY: Dict[str, Tool]` — name-to-instance mapping.

### 1.14 `ore/__init__.py` Exports

Source: `ore/__init__.py` `__all__` (33 names).

```
ARTIFACT_VERSION, ExecutionArtifact, run, ORE, Reasoner, AyaReasoner,
Message, Response, RoutingDecision, RoutingTarget, Router, RuleRouter,
TEST_ROUTING_TARGET, build_targets_from_registry, SkillMetadata,
build_skill_registry, build_targets_from_skill_registry,
load_skill_metadata, load_skill_instructions, load_skill_resource,
Session, SessionStore, FileSessionStore, fetch_models, default_model,
Tool, TOOL_REGISTRY, Gate, GateError, Permission, ToolResult
```

### 1.15 Version Strings (Current State)

| Location | Value |
|----------|-------|
| `ore/__init__.py` docstring | `"v0.9"` |
| `ore/cli.py` parser description | `"ORE v0.9 CLI"` |
| `ore/cli.py` interactive banner | `"ORE v0.9 interactive"` |
| `ore/cli.py` conversational banner | `"ORE v0.9 conversational"` |
| `ore/cli.py` single-turn header | `"--- ORE v0.9: Reasoning ---"` |
| `docs/foundation.md` title | `"v0.9"` |
| `docs/architecture.md` title | `"v0.9"` |
| `docs/invariants.md` title | `"v0.9"` |
| `ore.egg-info/PKG-INFO` | `Version: 0.3.2` **(STALE)** |
| `ore/__version__` | **DOES NOT EXIST** |
| `pyproject.toml` | **DOES NOT EXIST** (referenced in SOURCES.txt but missing from disk) |

### 1.16 Router Constants

Source: `ore/router.py`.

- `DEFAULT_CONFIDENCE_THRESHOLD = 0.5`
- `TEST_ROUTING_TARGET = RoutingTarget(name="echo", target_type="tool", description="Echo (test hint).", hints=["repeat this line"])`

### 1.17 Model Constants

Source: `ore/models.py`.

- `PREFERRED_MODELS = ("llama3.2", "llama3.1", "llama3", "mistral", "llama2", "qwen2.5")`

### 1.18 Gate Interface

Source: `ore/gate.py`.

- `Gate(allowed_permissions: frozenset[Permission])`
- `Gate.check(tool: Tool) -> None` (raises `GateError`)
- `Gate.run(tool: Tool, args: Dict[str, str]) -> ToolResult`
- `Gate.permissive() -> Gate` (classmethod; grants all permissions)
- `GateError(tool_name: str, missing: frozenset[Permission])`

---

## Phase 2 — Gap Analysis

Three-column table. For each contract item: is it documented? Is it tested? Is the test an `@pytest.mark.invariant`?

### 2.1 CLI Flags

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Flag names, types, defaults (§1.1) | YES (architecture.md, README.md) | PARTIAL (test_cli.py TestArgParsing checks some flags) | **NO** |
| Mutual exclusions (§1.2) | YES (invariants.md) | YES (test_cli.py TestModeValidation, TestArtifactCli) | **YES** (all 12 combinations) |

**Gap:** No test asserts the exact set of 20 flags, their types, or their defaults. A flag rename or default change would not be caught by an invariant test. Need a frozen-surface test.

### 2.2 Exit Codes

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Exit code meanings (§1.3) | **NO** | PARTIAL (some exit codes tested incidentally) | **NO** |

**Gap:** Major. Exit codes are not documented anywhere as a contract. No test asserts specific exit code values by category. Need: (a) document in interface lock, (b) add invariant tests for exit 0/1/2 semantics.

### 2.3 `--json` Output Schema

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Base keys: id, model_id, content, timestamp, metadata | Partially (architecture.md mentions) | YES (test_cli.py test_json_output_keys) | **NO** |
| Routing sub-object keys | Partially | YES (test_cli.py test_route_with_json_includes_routing_key) | **NO** |

**Gap:** Tests exist but are not marked `@pytest.mark.invariant`. Tests check key existence ("in data") but do not assert exact key sets (could silently gain extra keys). Need: promote to invariant, tighten assertions.

### 2.4 Execution Artifact Schema

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Schema (§1.5) | YES (docs/artifact-schema.md) | YES (test_types.py, test_cli.py) | PARTIAL (CLI conflict tests are invariant; schema shape tests are not) |
| Forward compatibility (unknown keys tolerated) | YES | YES (test_types.py test_forward_compat_tolerates_unknown_top_level_keys) | **NO** |
| `ARTIFACT_VERSION` value | YES | YES | **NO** |

**Gap:** Roundtrip and schema validation tests exist but are not invariant-marked. The artifact-schema.md is accurate against code. Need: promote key schema tests to invariant.

### 2.5 `ORE.execute()` / `ORE.execute_stream()`

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Signatures (§1.6) | YES (architecture.md, skills.md) | YES (test_core.py) | **NO** (signatures not explicitly tested) |
| One reasoner call per turn | YES (invariants.md) | YES | **YES** |
| Session append-only | YES (invariants.md) | YES | **YES** |
| Message list order (system, skill, tool, session, user) | YES (skills.md, architecture.md) | YES (test_core.py) | **NO** |
| Tool results turn-scoped | YES (invariants.md) | YES | **NO** (test exists, not invariant-marked) |
| Skill context turn-scoped | YES (invariants.md) | YES | **NO** (test exists, not invariant-marked) |

**Gap:** The one-call and append-only invariants are solid. Message order and turn-scoping tests exist but should be promoted to invariant. Signature stability is not tested (a parameter rename would not be caught).

### 2.6 Data Contracts (`ore/types.py`)

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Message fields (§1.7) | YES (architecture.md) | YES (test_types.py) | **NO** |
| Response fields | YES | YES | **NO** |
| Session fields | YES | YES | **NO** |
| ToolResult fields | YES (architecture.md) | YES (implicitly via gate/tool tests) | **NO** |
| RoutingTarget fields | YES | YES (implicitly) | **NO** |
| RoutingDecision fields | YES | YES (implicitly) | **NO** |
| SkillMetadata fields | YES | YES (test_skills.py) | **NO** |

**Gap:** No invariant test asserts the exact field set of any dataclass. A field rename or removal would be caught by usage tests but not by a dedicated contract test.

### 2.7 Session File Format

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| JSON shape (§1.8) | YES (architecture.md) | YES (test_store.py round-trip) | **NO** |

**Gap:** Round-trip test exists but does not assert exact JSON keys. Not invariant-marked.

### 2.8 Skill Format

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| YAML frontmatter keys (§1.9) | YES (architecture.md, skills.md) | YES (test_skills.py) | **NO** |
| Resource path traversal blocked | YES (invariants.md) | YES (test_skills.py) | **NO** (test exists, not marked) |

### 2.9 Permission Enum

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Exact enum values (§1.10) | YES (architecture.md) | **NO** (no test asserts exact set) | **NO** |

**Gap:** No test ensures the enum contains exactly these four values and no others.

### 2.10 Tool ABC / Reasoner ABC

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Tool ABC signatures (§1.11) | YES (architecture.md) | Implicit (via tool impls) | **NO** |
| Reasoner ABC signatures (§1.12) | YES (architecture.md, foundation.md) | YES (test_reasoner.py) | **NO** |
| Denied tool never executes | YES (invariants.md) | YES (test_gate.py) | **YES** |

### 2.11 `ore/__init__.py` Exports

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| `__all__` contents (§1.14) | YES (architecture.md lists exports) | **NO** | **NO** |

**Gap:** No test asserts the contents of `__all__`. A removed export would break downstream `import ore` users silently.

### 2.12 Version Strings

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Version propagation (§1.15) | **NO** (no single source of truth) | **NO** | **NO** |
| `pyproject.toml` / packaging | **STALE** (egg-info says 0.3.2; pyproject.toml missing from disk) | **NO** | **NO** |

**Gap:** Major. Version is hardcoded in 8+ locations. No `__version__` variable. No `pyproject.toml` on disk (was present per SOURCES.txt, now missing). Egg-info is at 0.3.2 while the codebase is at v0.9.

### 2.13 Router / Gate / Store

| Contract | Documented? | Tested? | Invariant? |
|----------|-------------|---------|------------|
| Router does not mutate targets | YES | YES | **YES** |
| `DEFAULT_CONFIDENCE_THRESHOLD = 0.5` | YES | YES (implicitly) | **NO** |
| Gate default-deny | YES | YES | **NO** (but denied-never-executes is invariant) |
| `SessionStore` ABC signatures | YES | YES (implicitly) | **NO** |

---

### Gap Summary — Priority Items

| # | Contract | Issue | Action |
|---|----------|-------|--------|
| G1 | Exit codes | Undocumented, untested as contracts | Document in interface lock; add invariant tests |
| G2 | `--json` output schema | Tests exist, not invariant-marked; key sets not exact | Promote tests; tighten to exact key assertions |
| G3 | CLI flag surface | No frozen-surface test for flag names/types/defaults | Add invariant test asserting minimum flag set + types |
| G4 | `ore/__init__.py` exports | Untested | Add invariant test for `__all__` minimum contents |
| G5 | Data contract field sets | Tests exist, not invariant-marked | Promote or add invariant tests for each dataclass |
| G6 | Version strings | No single source of truth; stale packaging metadata | Decision required (§3.4) |
| G7 | Permission enum values | No test for exact set | Add invariant test |
| G8 | Artifact schema shape | Tests exist, not invariant-marked | Promote to invariant |
| G9 | Turn-scoping (tool + skill) | Tests exist, not invariant-marked | Promote to invariant |
| G10 | Session file format | Round-trip tested, not invariant; no key assertion | Add invariant test for JSON shape |
| G11 | Tool ABC / Reasoner ABC signatures | Tested implicitly, not explicitly | Add signature-check invariant tests |
| G12 | Router constants | Tested implicitly | Add explicit invariant for threshold default |

---

## Phase 3 — Decision Log

Four decisions that must be resolved before implementation.

### Decision 1: Where does the interface lock document live?

**Options:**

- (a) New file: `docs/interface-lock.md`
- (b) New section in `docs/foundation.md`
- (c) Inline in `docs/invariants.md`

**Recommendation:** **(a) `docs/interface-lock.md`**

Rationale: The interface lock is a flat reference (tables of frozen contracts). `foundation.md` explains *why*; `invariants.md` explains *what must hold at runtime*. The interface lock says *what is frozen for consumers*. Different audiences, different documents. A separate file is discoverable and does not bloat existing docs.

**Needs answer from project owner.**

### Decision 2: How strict is the frozen-surface test?

**Options:**

- (a) Assert "parser has *at least* these flags" (allows additions, catches deletions/renames)
- (b) Assert "parser has *exactly* these flags" (catches accidental additions too)

**Recommendation:** **(a) Minimum surface + exact types/defaults**

Rationale: The roadmap says "additions allowed, mutations not." The test should assert that every flag in the inventory exists with its documented type and default, but should not reject new flags. For `__all__` and Permission enum, same principle: assert minimum membership, not exact.

**Needs answer from project owner.**

### Decision 3: Does `ore/__init__.py` get locked?

The `__init__.py` exports 33 names via `__all__`. If `import ore` becomes a first-class use case (Platform P4), the current export list is the proto-API.

**Options:**

- (a) Freeze the current `__all__` as a minimum set in v0.9.1 (additions allowed, removals not)
- (b) Leave `__all__` unfrozen until Platform P4

**Recommendation:** **(a) Freeze as minimum set**

Rationale: Removing an export is a breaking change regardless of whether P4 exists yet. Freezing the minimum set costs nothing and prevents accidental breakage. The invariant test would assert `set(expected) <= set(ore.__all__)`.

**Needs answer from project owner.**

### Decision 4: Version string propagation — single source of truth?

**Current state:** Version is hardcoded as `"v0.9"` or `"ORE v0.9 CLI"` in 8+ locations across `ore/cli.py`, `ore/__init__.py`, `docs/foundation.md`, `docs/architecture.md`, `docs/invariants.md`. There is no `__version__` variable. The `pyproject.toml` that was once present is now missing from disk, and `ore.egg-info/PKG-INFO` is stale at `Version: 0.3.2`.

**Options:**

- (a) Add `ore/__version__.py` (or `ore/_version.py`) with `__version__ = "0.9.1"` and reference it from `ore/__init__.py`, `cli.py`, and a restored `pyproject.toml` using `dynamic = ["version"]`
- (b) Hardcode the version in a restored `pyproject.toml` and read from `importlib.metadata` at runtime
- (c) Keep scattered hardcoded strings; update manually

**Recommendation:** **(a) `ore/_version.py`**

Rationale: A single-file version constant is the simplest approach for Python 3.10. It avoids runtime `importlib.metadata` overhead, works without an installed package, and is trivially importable. The `pyproject.toml` should also be restored (it was present before per SOURCES.txt) with `dynamic = ["version"]` pointing at this file, or with a static version that matches.

**Needs answer from project owner.**

---

## Phase 4 — Implementation Ordering

Once decisions are resolved, the implementation is mechanical.

### v0.9.1 — Interface Lock

Execute in this order:

| Step | Task | Depends on | Artifacts |
|------|------|------------|-----------|
| 1 | **Resolve decisions 1–4** | — | Decisions recorded in this document |
| 2 | **Add `ore/_version.py`** (if D4 = a) | D4 | New file: `ore/_version.py` with `__version__ = "0.9.1"` |
| 3 | **Restore `pyproject.toml`** | D4 | Restored file; version matches `_version.py` |
| 4 | **Update all version strings** to `0.9.1` | D4, step 2 | `ore/__init__.py`, `ore/cli.py` (5 locations), docs (3 files) |
| 5 | **Write interface lock document** | D1 | `docs/interface-lock.md` — flat tables from Phase 1 inventory |
| 6 | **Document exit codes** | G1 | Add exit code table to interface lock doc |
| 7 | **Add invariant test: CLI flag surface** | G3, D2 | `tests/test_cli.py` — assert minimum flag set with types and defaults |
| 8 | **Add invariant test: `--json` exact keys** | G2 | `tests/test_cli.py` — promote and tighten existing tests |
| 9 | **Add invariant test: exit code semantics** | G1 | `tests/test_cli.py` — assert exit 0 for `--list-*`, exit 1 for errors |
| 10 | **Add invariant test: `ore.__all__` minimum set** | G4, D3 | `tests/test_types.py` or new `tests/test_surface.py` |
| 11 | **Add invariant test: Permission enum values** | G7 | `tests/test_gate.py` — assert exact enum members |
| 12 | **Add invariant test: data contract fields** | G5 | `tests/test_types.py` — assert field names for Message, Response, Session, ToolResult, RoutingDecision, SkillMetadata, RoutingTarget |
| 13 | **Add invariant test: artifact schema keys** | G8 | `tests/test_types.py` — promote roundtrip test to invariant |
| 14 | **Promote existing tests to `@pytest.mark.invariant`** | G9 | `tests/test_core.py` — tool/skill turn-scoping tests; `tests/test_core.py` — message order test |
| 15 | **Add invariant test: session JSON shape** | G10 | `tests/test_store.py` — assert exact JSON keys on serialized session |
| 16 | **Add invariant test: Tool/Reasoner ABC signatures** | G11 | `tests/test_tools.py`, `tests/test_reasoner.py` — inspect abstract methods |
| 17 | **Add invariant test: router threshold default** | G12 | `tests/test_router.py` — assert `DEFAULT_CONFIDENCE_THRESHOLD == 0.5` |
| 18 | **Run full test suite** | All above | `pytest -v` — all green |
| 19 | **Run `black --check .`** | All above | Formatting clean |
| 20 | **Update `docs/invariants.md`** | All above | Add new invariant descriptions |
| 21 | **Final review** | All above | Every item in Phase 1 has a matching invariant test or is explicitly marked as non-frozen |

**Total new invariant tests: ~11.** Total test promotions: ~5.

### v1.0 — The Mainframe

Execute in this order:

| Step | Task |
|------|------|
| 1 | Update `ore/_version.py` to `"1.0.0"` |
| 2 | Update all version strings from `0.9.1` to `1.0` |
| 3 | Add "structurally complete" declaration to `docs/foundation.md` |
| 4 | Update `docs/roadmap.md` — move v0.9.1 and v1.0 to Completed |
| 5 | Run full test suite (`pytest -v`) |
| 6 | Run `black --check .` |
| 7 | Tag `v1.0.0` |

This is deliberately boring. The work is in v0.9.1.

---

## Existing `@pytest.mark.invariant` Tests (Current Count)

For reference, the tests already marked invariant:

| File | Count | Tests |
|------|-------|-------|
| `tests/test_core.py` | 5 | reasoner-once (execute), reasoner-once (stream), session-append-only, reasoner-once-with-tools, reasoner-once-with-skills |
| `tests/test_cli.py` | 18 | 7 mode-validation exclusions, 11 artifact flag exclusions |
| `tests/test_gate.py` | 1 | denied-tool-never-executes |
| `tests/test_router.py` | 2 | route-does-not-mutate-targets, route-does-not-mutate-skill-targets |
| **Total** | **26** | |

After v0.9.1, target is **~37–42 invariant tests**.

---

## Anti-patterns (Excluded)

- **No features in v1.0.** Multi-backend, thinking models, new tools — all Platform (P1–P5). This plan does not discuss them.
- **v0.9.1 ≠ v1.0.** v0.9.1 is the work (audit, tests, lock doc). v1.0 is the stamp (version bump + declaration). They are separate.
- **No skipped audit.** Phase 1 was done module-by-module against actual code, not docs.
- **Interface lock ≠ architecture.md.** The lock document is tables, not prose. Architecture explains *why*; the lock says *what is frozen*.
