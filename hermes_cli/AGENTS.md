# hermes_cli/ - Classic CLI, Config, and Skins

Use this guide when editing files under `hermes_cli/`.

## Key Files

- `commands.py` — central slash-command registry
- `main.py` — CLI entrypoint and profile bootstrap
- `config.py` — `DEFAULT_CONFIG`, env-var metadata, config loading/migration
- `setup.py` — interactive setup
- `tools_config.py` / `skills_config.py` — interactive configuration UIs
- `skin_engine.py` — data-driven theme/skin loading
- `model_switch.py` / `models.py` / `auth.py` — model/provider selection pipeline

## Slash Commands

- Add or change commands in `commands.py` first; registry is the source of truth.
- Then wire the handler in `cli.py`.
- Only if the command is also available in messaging should you add the gateway handler in `gateway/run.py`.
- Adding an alias normally means editing `CommandDef.aliases` only.

## Config Changes

- New config keys go through `DEFAULT_CONFIG`.
- New env vars go through `OPTIONAL_ENV_VARS` with metadata.
- Bump `_config_version` when existing user configs need migration.
- Remember there are multiple config consumers (`load_cli_config()`, `load_config()`, and gateway-side YAML reads); keep behavior aligned.

## UI / Skin Rules

- Skins are declarative data, not bespoke code paths.
- Keep user-skin overrides working; do not bake theme assumptions into CLI logic.
- Do **not** introduce `simple_term_menu`; use the existing curses-based patterns for interactive menus.
