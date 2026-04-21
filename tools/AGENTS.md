# tools/ - Built-in Tool Implementations

Use this guide when editing files under `tools/`.

## Core Rules

- Tool handlers must return JSON strings.
- Register tools through `registry.register(...)`.
- Toolset exposure is controlled from `toolsets.py`.
- If a tool stores runtime state, use `get_hermes_home()` for the base path.
- If a schema mentions user-visible paths, use `display_hermes_home()` so output remains profile-safe.

## Tool Schema Discipline

- Do **not** hardcode references to other tools in schema descriptions when those tools may be unavailable.
- If a cross-tool hint is needed, add it dynamically in `model_tools.py` where actual tool availability is known.

## Special Cases

- Agent-level tools such as `todo` and `memory` are intercepted before normal tool dispatch; do not force them through the generic path by accident.
- `_last_resolved_tool_names` is process-global; changes around delegation must preserve save/restore behavior.

## Validation

- When adding a tool, verify discovery, schema exposure, and dispatch.
- When changing tool schemas, test with realistic tool availability, not just static diffs.
