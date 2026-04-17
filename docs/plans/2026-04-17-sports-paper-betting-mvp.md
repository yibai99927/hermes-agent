# Sports Paper Betting MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a first paper-betting MVP that records and settles daily opening-line picks with strict daily caps: up to 3 football picks and up to 3 NBA picks.

**Architecture:** Extend the existing external script `~/.hermes/scripts/sports_data_system.py` instead of touching core app code. Keep the current collector/recommendation/backtest pipeline, then add four missing layers in order: market support expansion, candidate filtering/capping, paper-bet ledger + settlement, and a daily operator report.

**Tech Stack:** Python 3.11, external script under `~/.hermes/scripts`, SQLite, pytest repo-side tests, existing OddsPortal/OpenFootball/NBA collector.

---

## Current confirmed facts

1. Current live code supports only:
   - football `1X2`
   - basketball `moneyline`
2. Current live code does **not** yet support:
   - football handicap / totals
   - NBA spread / totals
3. Current live config only collects OddsPortal competition pages for:
   - Premier League
   - NBA
4. Current live system already has:
   - `report-recommendations`
   - `report-backtest`
   - `report-line-movements`
5. Current live system does **not** yet have:
   - paper bet ledger
   - simulated bankroll
   - bet placement command
   - daily cap enforcement
   - auto settlement for simulated bets

## Product decision for MVP

### Recommended MVP
Use a **half-automatic paper betting** workflow:
1. System generates candidates.
2. System enforces per-sport daily caps.
3. System stores approved paper bets in SQLite.
4. System settles finished bets automatically.
5. System outputs a daily paper-bet summary.

### Conservative backup
If expanded markets are unstable, keep paper betting on current supported markets first:
- football `1X2`
- NBA `moneyline`

Do **not** block the whole MVP on handicap/totals support if parsing those markets proves unstable.

## Important recommendation on market choice

For the first usable paper-betting MVP, do **not** start with all requested market types at once.

### Recommended first market set
- football: `totals` only
- NBA: `totals` only

Why:
- both are two-way markets
- easier ranking and settlement
- simpler than football handicap W/D/L
- less branching than supporting football three-way handicap plus multiple line values

### Second-wave market set
- football: handicap W/D/L
- NBA: spread

## Scope for v1

### Daily limits
- football: max 3 paper bets per day
- NBA: max 3 paper bets per day

### Filtering rules
- only opening-line style picks (`price_point=opener`)
- only within a fixed pregame window
- only one bet per event
- only one market per event
- sort by confidence/edge and keep the top N within caps

### Competition policy
- football must be restricted to mainstream leagues only
- NBA unrestricted within NBA source

Because the current live config only collects Premier League odds, the MVP must also add or explicitly plan support for more football leagues if “mainstream leagues” means more than EPL.

Suggested mainstream football allowlist for later config support:
- Premier League
- La Liga
- Bundesliga
- Serie A
- Ligue 1
- UEFA Champions League

## Required implementation layers

### Layer 1: market expansion
Add explicit support for these market families in the collector/recommendation path:
- football totals
- NBA totals
- optional later: football handicap W/D/L
- optional later: NBA spread

Minimum requirements:
- market type stored explicitly
- line value stored explicitly (example: `2.5`, `226.5`)
- selection labels normalized (example: `over`, `under`, `home`, `away`)
- settlement logic understands the market

### Layer 2: recommendation capping and policy
Add a new report/selection layer that:
- filters to `price_point=opener`
- filters by sport
- filters by allowed competitions
- filters by allowed market types
- limits daily output to:
  - 3 football bets max
  - 3 NBA bets max
- avoids duplicate event exposure

### Layer 3: paper-bet ledger
Add a dedicated SQLite table for simulated bets.

Suggested fields:
- `bet_id`
- `created_at`
- `bet_date`
- `status` (`open`, `settled`, `void`, `cancelled`)
- `sport`
- `league`
- `canonical_event_id`
- `event_time`
- `market`
- `line_value`
- `selection`
- `price_point`
- `offered_odds`
- `captured_at`
- `edge`
- `confidence`
- `stake_units`
- `source_report`
- `event_url`
- `result`
- `profit_units`
- `settled_at`
- `settlement_notes`

### Layer 4: settlement
Add automatic settlement for supported paper bets.

For totals markets:
- football: total goals vs line
- NBA: total points vs line

For later handicap/spread markets:
- football handicap W/D/L must respect line and three-way grading
- NBA spread must apply the spread and allow push handling

### Layer 5: daily operator report
Add a human-readable daily command that returns:
- today’s selected paper bets
- already open bets
- newly settled bets
- win/loss/push counts
- total profit units
- running bankroll or running paper PnL

## New CLI commands to add

### 1. `report-paper-candidates`
Purpose:
- return ranked, capped daily candidates

Key options:
- `--sports football,nba`
- `--football-limit 3`
- `--nba-limit 3`
- `--price-point opener`
- `--hours-ahead-min`
- `--hours-ahead-max`
- `--allowed-football-leagues`
- `--allowed-markets`
- `--json`

### 2. `paper-bet-place`
Purpose:
- store selected simulated bets in the ledger

Modes:
- `--auto-top` to place the top capped candidates
- `--bet-id` / `--canonical-event-id` for manual confirmation mode later

### 3. `paper-bet-settle`
Purpose:
- settle open simulated bets whose events are complete

### 4. `report-paper-bets`
Purpose:
- show open bets, settled bets, PnL, and status summary

## TDD task order

### Task 1: write failing tests for market metadata normalization
Test file:
- `tests/scripts/test_sports_data_system.py`

Start with failing tests for:
- totals market names are normalized
- line values are extracted and stored
- selection labels are normalized to `over` / `under`

### Task 2: implement market metadata extraction
Modify:
- `~/.hermes/scripts/sports_data_system.py`

### Task 3: write failing tests for capped paper candidates
Required behavior:
- football candidates capped at 3/day
- NBA candidates capped at 3/day
- duplicate same-event exposure rejected
- unsupported leagues rejected

### Task 4: implement `report-paper-candidates`
Modify:
- `~/.hermes/scripts/sports_data_system.py`

### Task 5: write failing tests for paper-bet ledger persistence
Required behavior:
- place paper bet from ranked candidates
- duplicate event bet rejected
- ledger row persists all required metadata

### Task 6: implement paper-bet ledger + `paper-bet-place`
Modify:
- `~/.hermes/scripts/sports_data_system.py`

### Task 7: write failing tests for settlement
Required behavior:
- football totals settle correctly
- NBA totals settle correctly
- profit units computed correctly
- unresolved games remain open

### Task 8: implement `paper-bet-settle`
Modify:
- `~/.hermes/scripts/sports_data_system.py`

### Task 9: write failing tests for daily operator report
Required behavior:
- report shows open bets
- report shows newly settled bets
- report shows running PnL and counts

### Task 10: implement `report-paper-bets`
Modify:
- `~/.hermes/scripts/sports_data_system.py`

### Task 11: verification
Run:
- `python3 -m py_compile /home/ubuntu/.hermes/scripts/sports_data_system.py`
- `source /home/ubuntu/.hermes/hermes-agent/venv/bin/activate && pytest tests/scripts/test_sports_data_system.py -q`

### Task 12: real dry-run verification
Run on live DB:
- candidate report
- paper-bet placement in paper mode
- settlement after sample completed events exist
- PnL report

## Non-goals for v1

Do not include these yet:
- real bookmaker automation
- Kelly sizing
- multi-bet parlays
- live in-play betting
- cross-book line shopping
- auto-send without human review

## Recommended rollout order

### Recommended route
1. football totals + NBA totals
2. capped paper candidates
3. paper ledger
4. settlement
5. daily summary
6. only then consider spread / football handicap W/D/L

### Conservative backup route
1. keep current `1X2` + `moneyline`
2. add paper ledger and settlement first
3. expand markets only after paper workflow is stable

## Verification standard

The feature is not done until all are true:
- targeted new tests fail first, then pass
- full sports test suite passes
- script compiles
- live candidate report returns sane capped output
- duplicate bet prevention works
- at least one sample bet can later settle end-to-end

## Notes for this repo/session

- Do not touch:
  - `cron/jobs.py`
  - `cron/scheduler.py`
  - `tests/cron/test_scheduler.py`
- Keep implementation isolated to:
  - `/home/ubuntu/.hermes/scripts/sports_data_system.py`
  - `/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`
  - optional plan/docs updates under `docs/plans/`
