# gateway/ - Messaging Gateway and Platform Adapters

Use this guide when editing files under `gateway/`.

## Key Surfaces

- `run.py` — message dispatch, slash-command routing, main gateway loop
- `session.py` — conversation/session persistence
- `platforms/` — Telegram, Discord, Slack, WhatsApp, Signal, etc.

## Rules

- Do not assume the gateway process cwd is the repo root; messaging flows may run from `MESSAGING_CWD` / `TERMINAL_CWD`.
- If a slash command is exposed in messaging, keep its behavior aligned with the central command registry.
- Background `terminal(background=true, notify_on_complete=true)` work relies on the gateway watcher; preserve the follow-up turn semantics.
- Respect `display.background_process_notifications` / `HERMES_BACKGROUND_NOTIFICATIONS` behavior when changing watcher output.
- Platform adapters with unique credentials should use scoped locks so two profiles cannot reuse the same bot token/API key concurrently.

## Validation

- For platform-specific changes, verify both dispatch behavior and user-visible formatting.
- For watcher changes, confirm completion notifications still trigger the expected follow-up turn.
