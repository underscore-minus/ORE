# ORE Execution Artifact Schema (v0.9.1)

Self-describing execution artifact produced by a single ORE turn. Enables chainable execution without runtime coupling: one execution produces an artifact; a platform consumes it and optionally feeds it into another.

## Version

- **Current:** `ore.exec.v1`
- **Constant:** `ARTIFACT_VERSION` in `ore/types.py`

## Schema

```json
{
  "artifact_version": "ore.exec.v1",
  "execution_id": "uuid",
  "timestamp": 1234567890.0,
  "input": {
    "prompt": "user prompt text",
    "model_id": "llama3.2:latest",
    "mode": "single_turn",
    "routing": { "target": "...", "target_type": "...", ... } | null,
    "tools": ["echo"] | null,
    "skills": ["skill-name"] | null
  },
  "output": {
    "id": "uuid",
    "content": "response text",
    "model_id": "llama3.2:latest",
    "timestamp": 1234567890.0,
    "metadata": {}
  },
  "continuation": {
    "requested": false,
    "reason": null
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact_version` | string | yes | Schema version for forward compatibility |
| `execution_id` | string | yes | Unique ID for this execution (matches output.id) |
| `timestamp` | number | yes | Unix timestamp (float) |
| `input` | object | yes | Context that produced this execution |
| `input.prompt` | string | yes | Original user prompt |
| `input.model_id` | string | yes | Model used |
| `input.mode` | string | yes | `"single_turn"` for v0.9 |
| `input.routing` | object \| null | no | Routing decision if --route was used |
| `input.tools` | array of string \| null | no | Tool names run this turn |
| `input.skills` | array of string \| null | no | Skill names activated this turn |
| `output` | object | yes | Reasoner response (Response shape) |
| `output.id` | string | yes | Response ID |
| `output.content` | string | yes | Response text |
| `output.model_id` | string | yes | Model that produced the response |
| `output.timestamp` | number | yes | Response timestamp |
| `output.metadata` | object | yes | Reasoner metadata (eval_count, etc.) |
| `continuation` | object | yes | Declared signal only, never inferred |
| `continuation.requested` | boolean | yes | True if output explicitly asked for follow-up |
| `continuation.reason` | string \| null | no | Optional explanation |

## Non-goals (v0.9)

- **No embedded session history replay** — Single-turn only; conversational artifacts deferred.
- **No hidden execution directives** — Continuation is declared, never inferred from content.
- **No engine-side invocation** — ORE does not call or orchestrate other ORE instances.
- **Chaining via data only** — Platform consumes artifact; engine is ignorant of what happens after output.

## CLI Contract

- **Emit:** `--artifact-out [PATH]` — Write artifact JSON. `-` or omit value for stdout; path for file. Single-turn only; incompatible with `--stream`. When stdout, output is artifact JSON only.
- **Consume:** `--artifact-in PATH` — Read artifact from file or `-` (stdin). Use `input.prompt` for the turn. Single-turn only; mutually exclusive with prompt, `--tool`, `--route`, `--skill`, REPL modes.

## Forward Compatibility

- Unknown top-level keys in the artifact are tolerated on parse.
- New schema versions require a version bump; consumers should check `artifact_version` before processing.
