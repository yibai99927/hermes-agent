# agent/ - Runtime Internals

Use this guide when editing files under `agent/`.

## Key Surfaces

- `prompt_builder.py` — system prompt pieces, context-file loading, skill index prompt
- `context_compressor.py` — the normal path for shrinking/repacking conversation context
- `prompt_caching.py` — cache controls; keep stable prefixes stable
- `auxiliary_client.py` — auxiliary model calls (vision, summarization, compression)
- `display.py` — CLI rendering, spinner, tool activity output
- `skill_commands.py` — slash-command skill injection shared by CLI/gateway

## Rules

- Do not move dynamic or user-specific data into the stable system prompt if it can stay in a user/tool message instead.
- Preserve context-file security scanning and truncation behavior when touching `prompt_builder.py`.
- Any change that rewrites prior context or changes tool availability mid-session is cache-breaking unless it is part of the explicit compression flow.
- `skill_commands.py` should keep skill content injected as a **user message**, not a system-prompt mutation.
- For `display.py`, do **not** use `\033[K`; pad with spaces so output works under `prompt_toolkit` patching.

## Validation

- If prompt assembly changed, run the focused prompt-builder tests.
- If cache behavior changed, verify that prompt prefixes remain stable across turns.
- If display changed, check CLI rendering rather than trusting diffs alone.
