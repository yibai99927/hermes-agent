# Hermes Agent - Development Guide

Global repo context for AI coding assistants working on `hermes-agent`.
Keep this file short: only cross-repo rules that should apply before any subtree `AGENTS.md` is discovered.

## Development Environment

```bash
source venv/bin/activate
```

## Core Repo Map

- `run_agent.py` — `AIAgent` bootstrap, conversation loop, prompt assembly wiring
- `model_tools.py` — tool discovery, schema post-processing, dispatch glue
- `toolsets.py` — toolset membership and exposure
- `agent/` — prompt builder, compression, auxiliary client, display, shared runtime internals
- `hermes_cli/` — classic CLI, slash commands, config/setup, skins
- `tools/` — built-in tool implementations and registry
- `gateway/` — messaging gateway and platform adapters
- `ui-tui/` + `tui_gateway/` — Ink TUI frontend + Python JSON-RPC backend
- `tests/` — hermetic pytest suite
- `batch_runner.py` — isolated batch processing without user memory/context files

## Global Engineering Rules

### Prompt caching must not break
Do **not** implement changes that:
- alter prior context mid-conversation
- change toolsets mid-conversation
- reload memories or rebuild the system prompt mid-conversation

The only normal context rewrite path is context compression.

### Use profile-safe paths
- Use `get_hermes_home()` for runtime state under `HERMES_HOME`
- Use `display_hermes_home()` for user-facing path text
- Do **not** hardcode `~/.hermes` or `Path.home() / ".hermes"` for runtime state

### Respect runtime cwd behavior
- CLI uses the current shell directory
- Messaging/gateway flows may use `MESSAGING_CWD` / `TERMINAL_CWD`
- Do not assume the gateway process is running from the repo root

### Testing defaults
- Default test entrypoint: `scripts/run_tests.sh`
- Use raw `pytest` only when the wrapper is impossible, and then mirror CI as closely as possible
- Run the full relevant suite before pushing

## Global Pitfalls

- Do **not** use `\033[K` in spinner/display code; use space-padding instead
- `_last_resolved_tool_names` in `model_tools.py` is process-global; child-agent execution saves/restores it around delegation
- Keep this root file global only; module-specific implementation detail belongs in subtree `AGENTS.md`

## Subtree Guides

When work concentrates in one area, the agent should rely on the nearest subtree guide:
- `agent/AGENTS.md` — prompt builder, compression, display, runtime internals
- `hermes_cli/AGENTS.md` — CLI commands, config, skins, setup flows
- `tools/AGENTS.md` — tool authoring, schemas, state paths
- `gateway/AGENTS.md` — platform adapters, watcher behavior, gateway dispatch
- `ui-tui/AGENTS.md` — Ink frontend contract
- `tui_gateway/AGENTS.md` — Python RPC backend for the TUI
- `tests/AGENTS.md` — hermetic test rules and profile-test patterns
