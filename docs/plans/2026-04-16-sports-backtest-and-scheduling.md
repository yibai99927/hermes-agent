# Sports Backtest and Scheduling Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为现有 sports_data_system.py 增加第一版回测报表与固定窗口调度落地方案，让推荐从“会生成”升级为“能复盘”。

**Architecture:** 复用现有 recommendation heuristic，不重新设计模型。回测只评估数据库里已经有赔率快照和完赛比分的事件；为避免数据穿越，回测必须使用“下注当时可见”的 feature snapshot，而不是事后最新快照。调度先以最稳的 cron/Hermes cron 为主，围绕固定赛前窗口做 opener/latest 采集与报表。

**Tech Stack:** Python 3、SQLite、pytest、Hermes cronjob、现有 sports_data_system.py CLI。

---

### Task 1: 写回测失败测试
- 文件：`/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`
- 覆盖点：
  - 能把 recommendation 结算成 win/loss 和 ROI
  - 使用下注时点可见的 feature snapshot，防止后补历史数据污染回测

### Task 2: 在脚本中补回测核心 helper
- 文件：`/home/ubuntu/.hermes/scripts/sports_data_system.py`
- 新增 helper：
  - 赔率转 decimal
  - 赛果映射为 home/draw/away
  - 提取完赛事件结果
  - 选择 `generated_at <= captured_at` 的 feature snapshot
  - 复用 recommendation 逻辑生成可结算 bet candidates

### Task 3: 新增 `report-backtest` CLI
- 文件：`/home/ubuntu/.hermes/scripts/sports_data_system.py`
- 参数尽量与 `report-recommendations` 对齐：
  - `--price-point`
  - `--hours-ahead-min`
  - `--hours-ahead-max`
  - `--min-edge`
  - `--min-recent-matches`
  - `--limit`
  - `--json`
- 输出：
  - settled_recommendation_count
  - wins / losses / pushes
  - hit_rate_pct
  - total_profit_units
  - roi_pct
  - bets 明细

### Task 4: 验证
- 先跑新增测试到绿
- 再跑全量 `tests/scripts/test_sports_data_system.py`
- 再在真实数据库上跑 `report-backtest`，确认当前是否有可结算样本；若样本不足，要明确说明是数据覆盖边界，不是假装有结果。

### Task 5: 固定窗口调度落地
- 文件：
  - `docs/plans/2026-04-16-sports-backtest-and-scheduling.md`
  - 优先不侵入核心 cron 脏文件；给出可直接创建的 Hermes cronjob
- 默认调度：
  1. 定时 `collect`
  2. 固定窗口跑 `report-recommendations --price-point opener`
  3. 次日/赛后跑 `report-backtest`
- 若真实库暂时无 settled odds sample，要说明“调度先积累样本，回测框架已可用”。
