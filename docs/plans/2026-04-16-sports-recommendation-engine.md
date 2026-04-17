# Sports Recommendation Engine Implementation Plan

> For Hermes: implement in TDD order; do not touch cron/jobs.py, cron/scheduler.py, tests/cron/test_scheduler.py.

Goal: 在现有免费体育数据底座上，补一个“第一版可运行的赛前推荐层”，支持 latest / opener 两种价格口径，并支持“开赛前固定时点窗口”筛选。

Architecture:
- 继续只改 ~/.hermes/scripts/sports_data_system.py 与 tests/scripts/test_sports_data_system.py
- 不做黑盒 ML；先做可解释、可验证的 heuristic recommendation engine
- 推荐输出不是“保证盈利”的承诺，而是“基于近期状态 + 当前/初盘赔率”的 value 候选清单

Tech stack:
- Python 3.11
- sqlite3
- 现有 odds_snapshots / feature_snapshots / event_links / normalized_items

---

## Scope

第一版只做：
1. 赔率转 implied probability
2. no-vig 市场概率
3. 基于近期 form 的简化模型概率
4. edge/value ranking
5. price_point=latest|opener
6. 固定时点窗口：hours_ahead_min / hours_ahead_max
7. CLI: report-recommendations

不做：
- 回测收益曲线
- Kelly 资金管理执行
- 临场实时推荐
- 自动下单

## Data contract

Input:
- feature_snapshots: recent_form_v1
- odds_snapshots: earliest/latest price per canonical event

Output per recommendation:
- canonical_event_id
- sport / league / teams / event_time
- market
- price_point (latest/opener)
- selection (home/draw/away)
- offered_odds
- market_implied_prob
- model_prob
- edge
- confidence
- reasons[]

## Heuristic model (v1)

### Football 1X2
- home_ppm = home_recent_points / max(home_recent_matches, 1)
- away_ppm = away_recent_points / max(away_recent_matches, 1)
- home_gdpm = (home_recent_goals_for - home_recent_goals_against) / max(home_recent_matches, 1)
- away_gdpm = (away_recent_goals_for - away_recent_goals_against) / max(away_recent_matches, 1)
- strength_gap = (home_ppm - away_ppm) + 0.35 * (home_gdpm - away_gdpm) + 0.25
- draw_prob = clamp(0.28 - 0.08 * abs(strength_gap), 0.12, 0.28)
- remaining = 1 - draw_prob
- home_prob = sigmoid(strength_gap) * remaining
- away_prob = remaining - home_prob

### Basketball moneyline
- home_ppm = home_recent_points / max(home_recent_matches, 1)
- away_ppm = away_recent_points / max(away_recent_matches, 1)
- home_gdpm = (home_recent_goals_for - home_recent_goals_against) / max(home_recent_matches, 1)
- away_gdpm = (away_recent_goals_for - away_recent_goals_against) / max(away_recent_matches, 1)
- strength_gap = (home_ppm - away_ppm) + 0.20 * (home_gdpm - away_gdpm) + 0.15
- home_prob = sigmoid(strength_gap)
- away_prob = 1 - home_prob

### Recommendation rule
- market probs = no-vig normalization from offered odds
- edge = model_prob - market_prob
- keep only edge >= min_edge
- confidence = min_recent_matches / recent_form_match_limit adjusted by abs(edge)

## Tasks

### Task 1: write failing tests
- add recommendation helper tests
- cover latest vs opener price point
- cover fixed window filtering
- cover football 1X2 recommendation ranking

### Task 2: add probability helpers
- implied prob from American odds
- no-vig normalization
- fair odds formatting
- logistic probability helper

### Task 3: add snapshot selection helpers
- resolve latest odds snapshot per event
- resolve opener odds snapshot per event
- join with latest feature snapshot
- ignore summary-only rows with missing teams/event_time

### Task 4: add heuristic model
- football 1X2 model
- basketball moneyline model
- edge / confidence / reasons generation

### Task 5: add CLI
- report-recommendations
- flags: --price-point latest|opener, --hours-ahead-min, --hours-ahead-max, --min-edge, --limit

### Task 6: verify
- pytest tests/scripts/test_sports_data_system.py -q
- python3 -m py_compile ~/.hermes/scripts/sports_data_system.py
- real collect
- real report-recommendations latest
- real report-recommendations opener
