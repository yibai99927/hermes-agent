# Sports Data Collector 实施计划

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

目标：在不改 Hermes 核心框架的前提下，落地一套可直接运行的体育数据采集系统，优先支持免费数据源，并为 API-Football / SportsDataIO 预留可启用接口与注册说明。

架构：采用“外部脚本 + 本地状态目录 + 仓库测试”方案。运行时代码放在 `/home/ubuntu/.hermes/scripts/sports_data_system.py`，数据持久化落到 `~/.hermes/sports-data/`；仓库内只新增测试和计划文档，避免碰当前已脏的 cron 相关改动。

技术栈：Python 3.11、sqlite3、urllib、可选 `nba_api`、pytest。

---

## 推荐方案 vs 保守备选

### 推荐方案（优先）
1. 单文件脚本实现数据源抽象、配置初始化、SQLite 存储、CLI 命令。
2. 免费源默认启用：`nba_api`、OpenFootball、OddsPortal 页面快照。
3. 付费/注册源默认禁用：API-Football、SportsDataIO，仅在配置与环境变量齐备后启用。

优点：
- 不污染 Hermes 核心代码。
- 易于 cron 化。
- 测试可直接覆盖外部脚本行为。

### 保守备选
只做一个抓取脚本，不做配置文件和数据库，只输出 JSON。

缺点：
- 难扩展多源。
- 难做失败诊断和后续分析。

推荐顺序：先做推荐方案。

---

## 目标产物

### A. 运行脚本（必须）
Create: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

能力：
- 自动创建默认配置与数据目录
- `doctor`：检查依赖、配置、环境变量、注册源状态
- `collect`：执行多源采集并落盘
- `instructions`：输出 API-Football / SportsDataIO 注册与启用步骤
- 统一输出 JSON 摘要

### B. 测试（必须）
Create: `/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`

覆盖：
- 默认配置创建
- OpenFootball 解析
- OddsPortal 页面摘要解析
- 多源采集结果写入 SQLite 与原始快照
- 注册说明输出

### C. 运行时目录（自动创建）
- `~/.hermes/sports-data/config/sources.json`
- `~/.hermes/sports-data/state/collector.db`
- `~/.hermes/sports-data/raw/<run-id>/...json`

---

## 实施任务

### Task 1: 写失败测试，定义脚本外部契约
文件：
- Create: `/home/ubuntu/.hermes/hermes-agent/tests/scripts/test_sports_data_system.py`

步骤：
1. 定义 `load_config()` 自动建默认配置的测试。
2. 定义 `OpenFootballSource.parse_payload()` 的解析测试。
3. 定义 `OddsPortalSource.extract_page_summary()` 的解析测试。
4. 定义 `collect_all()` 写 SQLite 与 raw snapshot 的测试。
5. 运行 `pytest tests/scripts/test_sports_data_system.py -q`，预期先失败。

### Task 2: 实现最小脚本骨架让配置测试通过
文件：
- Create: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

步骤：
1. 实现路径常量、默认配置、`load_config()`、`save_config()`。
2. 实现 `registration_instructions()`。
3. 重跑单测直到配置相关测试通过。

### Task 3: 实现源解析与持久化
文件：
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

步骤：
1. 实现 `BaseSource`、`OpenFootballSource`、`OddsPortalSource`。
2. 实现 SQLite 初始化与 run/snapshot 写入。
3. 实现 `collect_all()` 聚合与 JSON 摘要。
4. 重跑测试直到通过。

### Task 4: 实现 CLI 命令与注册源占位接口
文件：
- Modify: `/home/ubuntu/.hermes/scripts/sports_data_system.py`

步骤：
1. 加入 `doctor` / `collect` / `instructions` 命令。
2. 加入 API-Football / SportsDataIO 配置、环境变量检查、说明文本。
3. 保持默认禁用，避免无 key 时报错。

### Task 5: 验证真实运行
文件：
- 无新增文件，运行验证命令

步骤：
1. 运行 `python3 /home/ubuntu/.hermes/scripts/sports_data_system.py doctor`
2. 运行 `python3 /home/ubuntu/.hermes/scripts/sports_data_system.py collect --dry-run`
3. 运行 `pytest tests/scripts/test_sports_data_system.py -q`
4. 如无异常，再给用户注册步骤与后续 cron 接法。

---

## 验收标准

- 默认运行不需要 API key。
- 默认配置里明确存在 `api_football` 与 `sportsdataio` 两个 disabled source。
- 至少一个真实免费源可跑通并落盘。
- 测试全部通过。
- 不修改当前脏文件：`cron/jobs.py`、`cron/scheduler.py`、`tests/cron/test_scheduler.py`。
