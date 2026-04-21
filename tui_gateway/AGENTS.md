# tui_gateway/ - Python RPC Backend for the TUI

Use this guide when editing files under `tui_gateway/`.

## Architecture

- `tui_gateway/` owns Python-side sessions, tools, slash-command execution, and JSON-RPC handling for `ui-tui/`.
- The TUI protocol is shared with the Ink frontend; stability matters more than local convenience.

## Rules

- Keep request/event names aligned with the frontend.
- Slash commands should continue using the persistent `_SlashWorker` / command-dispatch path rather than ad-hoc one-off execution.
- Do not duplicate frontend-only behavior here; keep backend responsibilities focused on sessions, tools, approvals, and RPC transport.

## Validation

- Verify RPC method compatibility with `ui-tui/` after protocol changes.
- Check slash-command flows end-to-end when modifying worker or dispatch behavior.
