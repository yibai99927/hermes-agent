# Sports Opener vs Latest Line Movement Report Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为现有 sports_data_system.py 增加 opener vs latest 差异报表，帮助判断盘口从首个快照到最新快照的移动方向和幅度。

**Architecture:** 复用已有 odds_snapshots 表，不新增数据源、不重做推荐模型。报表按 event_key + market 聚合整条赔率序列，对比 opener 与 latest 两个端点，输出各 selection 的 implied probability 变化、overround 变化、最大移动项，并支持固定赛前窗口与 changed-only 过滤。

**Tech Stack:** Python 3、SQLite、pytest、现有 sports_data_system.py CLI。

---

### Task 1: 写失败测试
- 文件：`/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`
- 覆盖点：
  - 同一赛事/市场能正确对比 opener 与 latest
  - 会按最大 implied probability 变化排序
  - 支持 fixed pregame window / changed-only 过滤

### Task 2: 在脚本中补 line movement helper
- 文件：`/home/ubuntu/.hermes/scripts/sports_data_system.py`
- 新增 helper：
  - 读取完整 odds series
  - 计算 overround
  - 产出 selection 级别 opener/latest 差异
  - 计算 biggest_move_selection 与 max_abs_implied_prob_delta

### Task 3: 新增 `report-line-movements` CLI
- 文件：`/home/ubuntu/.hermes/scripts/sports_data_system.py`
- 参数：
  - `--hours-ahead-min`
  - `--hours-ahead-max`
  - `--changed-only`
  - `--limit`
  - `--json`
- 输出：
  - series_count / changed_series_count / unchanged_series_count
  - movements 明细
  - opener/latest captured_at 与 odds/probability 变化

### Task 4: 验证
- 先跑新增 targeted tests 到绿
- 再跑全量 `tests/scripts/test_sports_data_system.py`
- 再跑 `py_compile`
- 最后在真实数据库上运行 `report-line-movements --json`，确认有真实变化样本输出，不要只停留在单测。
