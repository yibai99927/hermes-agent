# ui-tui/ - Ink Frontend

Use this guide when editing files under `ui-tui/`.

## Architecture

- The TUI is the screen owner.
- `ui-tui/` renders transcript, composer, prompts, activity, and local client commands.
- It communicates with `tui_gateway/` over newline-delimited JSON-RPC.

## Rules

- Keep the frontend/backend contract in sync with `tui_gateway/`.
- Built-in client-only commands stay local in the Ink app.
- Everything else should continue flowing through `slash.exec` / command dispatch rather than duplicating business logic in TypeScript.
- Theme and branding data come from the backend-ready payload; avoid hardcoding presentation assumptions that bypass the shared skin model.

## Validation

- Run the relevant `npm` checks for this package when changing UI behavior.
- If you change RPC payloads or event names, validate the paired `tui_gateway/` changes together.
