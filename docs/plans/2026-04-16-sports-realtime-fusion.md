# 体育数据“准实时 + 融合层”实施计划

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

目标：把当前 `sports_data_system.py` 从“研究型采集器”升级成“准实时数据底座 + 多源融合层”，重点补齐两件事：
1. 准实时采集、重试、时序落盘、可观测性
2. 多源赛事对齐、球队名标准化、历史/近期特征表

重要边界：
- 不承诺“所有有用数据 100% 实时可得”，尤其在免费源约束下无法保证。
- 推荐目标应定义为：`尽可能低延迟 + 可观测 + 可补采 + 可验证的数据系统`。
- 如果用户允许接入付费源，实时性和完整性会明显提升；若坚持免费优先，则只能做到“准实时”而非“全量实时”。

架构：在不碰当前脏的 `cron/jobs.py` / `cron/scheduler.py` / `tests/cron/test_scheduler.py` 前提下，继续沿用“外部脚本 + 本地状态目录 + 仓库测试”方案。运行时仍放在 `/home/ubuntu/.hermes/scripts/sports_data_system.py`，并在 `~/.hermes/sports-data/` 下新增融合层状态、时间序列表与健康指标。

技术栈：Python 3.11、sqlite3、urllib、BeautifulSoup、pytest、Hermes cronjob（后续调度）、可选付费 API 源。

---

## 推荐方案 vs 保守备选

### 推荐方案（优先）
目标：做“准实时、可补采、可回放、可融合”的数据系统。

包含：
1. 增量轮询与 source health
2. 盘口时间序列（同场比赛多次抓取）
3. 赛事主键对齐层（跨源 match linking）
4. 球队名标准化映射
5. 近期状态 / 历史战绩特征表
6. cron 定时执行与失败告警
7. 允许后续接入 1~2 个付费/注册源提升实时性

优点：
- 真正朝“可下注前分析”靠近
- 后续接推荐/回测层更顺
- 能定位数据延迟、缺口和异常

缺点：
- 工程量明显高于当前采集器
- 如果坚持免费源，实时性仍有上限

### 保守备选
目标：只补“时间序列 + 赛事对齐”，不做稳定调度和可观测。

优点：
- 上手更快
- 改动更少

缺点：
- 很快卡在“能抓，但不稳、不知道什么时候坏了”
- 后面还得返工补 observability / retry / cron

推荐顺序：先做推荐方案。

---

## 本阶段明确不做的事

1. 不直接做投注推荐引擎
2. 不先做机器学习模型
3. 不先做资金管理或凯利公式
4. 不改 Hermes 主 cron 核心文件

原因：数据底座和融合层没稳定之前，上层推荐会失真。

---

## 目标产物

### A. 运行脚本增强
Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

新增能力：
- `collect-loop-once` / `collect-realtime` 模式
- source 重试、超时、退避
- source health 摘要
- odds snapshot 时间序列落盘
- fixture linking（跨源赛事对齐）
- team alias normalization
- feature materialization（近期状态、主客场、近 N 场）
- `report-health` / `report-linking` / `report-features` 命令

### B. 测试增强
Modify/Create: `/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`

新增覆盖：
- 轮询重试与失败状态
- 盘口快照时间序列写入
- 同一赛事多源对齐
- 球队别名标准化
- 近期特征表构建
- 报表输出

### C. 运行时目录扩展
Under `~/.hermes/sports-data/`:
- `config/sources.json`（新增 polling 与 linking 配置）
- `state/collector.db`（新增 linking / odds_timeseries / feature 表）
- `raw/<run-id>/...json`
- `reports/health/`
- `reports/linking/`
- `reports/features/`

---

## 拆解任务

### Task 1: 定义“准实时 + 融合层”测试契约
Objective: 先把目标行为写成失败测试，锁定边界。

Files:
- Modify: `/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`

要补的测试：
1. source 连续失败时写出 health 状态
2. 同一场比赛多次抓取，写入 odds_timeseries 而不是覆盖
3. API-Football fixture 与 OddsPortal event 可通过标准化名称 + 时间窗对齐
4. 近期 5 场 / 主客场统计特征能从历史数据 materialize 出来
5. CLI 报告命令能输出 data freshness / missing links / feature coverage

验证：
- `source venv/bin/activate && pytest tests/scripts/test_sports_data_system.py -q`
- 预期：新增测试先失败

### Task 2: 扩数据库 schema，支持时间序列与融合层
Objective: 让底层存储能承接“准实时”和“多源对齐”。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

新增表建议：
1. `source_health`
2. `odds_snapshots`
3. `event_links`
4. `team_aliases`
5. `feature_snapshots`

最小字段：
- `odds_snapshots`: run_id, source_name, event_key, market, odds_json, captured_at
- `event_links`: canonical_event_id, source_name, external_id, confidence, linked_at
- `team_aliases`: raw_name, normalized_name, sport, league_hint
- `feature_snapshots`: canonical_event_id, feature_set, feature_json, generated_at

### Task 3: 加 source polling / retry / health 逻辑
Objective: 把现在的一次性 collect 变成可连续运行的准实时采集器。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

新增逻辑：
1. 每个 source 定义 polling interval / timeout / max_retries
2. 单次失败写入 `source_health`
3. 连续失败计数 / 最近成功时间 / 最近错误
4. CLI: `doctor` 中增加 freshness / health 输出
5. CLI: `collect-realtime --iterations N --sleep-sec M`

### Task 4: 实现赔率时间序列落盘
Objective: 同一赛事的盘口变化可追踪。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

步骤：
1. 为 OddsPortal / 未来赔率源生成稳定 `event_key`
2. 每次抓取都新增一条 odds snapshot
3. 保留 market_headers / odds / event_time / event_url / captured_at
4. 提供简单查询命令：`report-odds-timeseries`

### Task 5: 实现球队标准化与赛事对齐层
Objective: 把不同源里的同场比赛链接起来。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

步骤：
1. 先做简单规则标准化：
   - 小写
   - 去 FC / CF / AFC / 标点 / 多余空格
   - 常见缩写映射
2. 先做足球/篮球各自规则
3. 用 `league + normalized_home + normalized_away + date window` 做首次 linking
4. 记录 confidence，低置信度不硬链
5. 提供 `report-linking`，列出未对齐赛事

### Task 6: 构建近期/历史特征表
Objective: 让数据从“原料”变成“可分析输入”。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

第一批特征只做最有用、最稳的：
1. 近 5 场战绩
2. 近 5 场进球/失球（足球）
3. 主客场近 5 场拆分
4. 最近比赛间隔天数
5. 历史交锋基础计数（若可得）

注意：
- 先不碰伤停、首发、赛程强度高级建模
- 先做 deterministic features

### Task 7: 报表与健康检查
Objective: 让系统可判断“哪些数据够用、哪些还不够”。

Files:
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

新增命令：
1. `report-health`
2. `report-linking`
3. `report-features`
4. `report-freshness`

输出要能回答：
- 哪个 source 最后成功时间
- 哪些联赛/比赛盘口抓到了
- 哪些比赛缺 link
- 哪些比赛已有 feature snapshot

### Task 8: 接 cron 做稳定调度（不改现有脏文件）
Objective: 用用户侧 cronjob 先跑通，而不是碰主仓库 cron 核心文件。

Files:
- Create/Modify: `~/.hermes/scripts/` 下辅助脚本或直接使用 Hermes cronjob

调度建议：
1. 高频赔率源：5~15 分钟一次（视源限制）
2. 历史/结构化补数：每天 1~4 次
3. 失败时保留 health 记录，不要静默

---

## 验收标准

最低可接受：
1. 同一赛事的盘口可形成时间序列
2. 至少一条免费赔率源 + 一条结构化比赛源能自动对齐一部分赛事
3. 能生成近期状态特征
4. 有 source freshness / health 报告
5. 定向测试 + 全量 sports_data_system 测试通过

更高标准：
1. cron 连续运行 24h 无崩溃
2. 可输出“哪些赛事缺盘口 / 缺历史 / 缺 link”的缺口报告
3. 后续能无缝接推荐层

---

## 风险与现实边界

1. 免费源无法保证“所有有用数据都实时”
2. OddsPortal DOM 结构可能漂移
3. API-Football 免费版当前赛季权限受限
4. 伤停 / 阵容 / 临场线等高价值数据，通常需要更多源或付费补强

因此：
- 如果用户坚持免费优先，目标表述必须是“准实时分析底座”
- 如果用户允许少量付费，才有机会接近“下注前实时分析”

---

## 推荐执行方式

推荐按两阶段推进：

### 阶段 1（本周）
- Task 1~5
- 先把 polling / timeseries / linking 做起来

### 阶段 2（随后）
- Task 6~8
- 把 features / reports / cron 完整接上

这样做的原因：
- 先把实时底座和事件对齐打通
- 再做上层特征，不然特征会建在脏数据上
