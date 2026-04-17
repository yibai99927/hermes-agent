# Research Digest 健康状态 + Watchlist 实施计划

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

目标：为当前每天 08:00 的学术晨报增加两类能力：失败告警/质量自检，以及作者/实验室/会议 watchlist；并把 Gmail Scholar 已关注作者自动纳入 watchlist。

架构：不改 Hermes 核心框架，先在现有用户侧自动化上增强。推荐把“候选抓取/状态持久化”和“日报生成”分层：前置脚本负责抓数据、维护 watchlist、产出健康状态 JSON；cron 晨报负责消费这些状态并在 Telegram/本地归档中显式展示。

技术栈：Python 3.11、Gmail API（现有 google_api.py）、arXiv API、Hermes cronjob、JSON 持久化、本地 Markdown 归档。

---

## 推荐方案 vs 保守备选

### 推荐方案（优先）
把能力拆成“状态层 + 展示层”：
1. `scholar_digest_input.py` 负责抓 Gmail/arXiv、更新 watchlist、写 health/state JSON。
2. cron prompt 只负责读这些结构化状态、抓正文、生成日报。

优点：
- 状态可复用，可回溯。
- 失败原因能稳定落盘，不靠 LLM 临时总结。
- 后续加周报/月报、趋势统计更容易。

### 保守备选
把健康状态和 watchlist 都直接塞进当前 `scholar_digest_input.py` 输出，不新增 state/config 文件，只更新 raw JSON 与 cron prompt。

缺点：
- 逻辑更快变成一坨。
- watchlist 无法稳定积累历史命中和连续命中次数。

推荐顺序：先做推荐方案；只有你想极限压缩改动量时才选保守备选。

---

## 当前已确认的现实约束

1. 当前候选抓取入口已经存在：`/home/ubuntu/.hermes/scripts/scholar_digest_input.py`
2. 当前 cron 任务已经存在：`job_id=6ac7b7bce4ce`
3. 当前原始候选快照已经落盘：`~/.hermes/research-digest/raw/YYYY-MM-DD.json`
4. Gmail Scholar 邮件可稳定命中，主题形如：`<作者名> - 新文章`
5. 这意味着“自动从 Gmail 已关注作者导入 watchlist”不需要新数据源，直接复用现有 Gmail 查询即可。

---

## 目标产物

### A. 健康状态（必须）
日报里新增固定块：
- Gmail：正常 / 无邮件 / API 失败 / 解析失败
- arXiv：正常 / 失败 / 结果为 0
- 今日候选数：Gmail、arXiv、去重后 combined
- 候选量告警：过少 / 正常 / 过多
- 正文获取率：X / Y（百分比）
- 是否回退为 arXiv-only：是 / 否
- 日报健康状态：healthy / degraded / failed

### B. Watchlist（必须）
支持三类 watchlist：
- authors
- labs
- venues（会议/期刊/arXiv category）

并支持：
- Gmail Scholar 主题里的关注作者自动加入 `authors.auto_followed`
- 记录 first_seen / last_seen / source / hit_count / recent_hit_streak
- 晨报排序时给 watchlist 命中加权
- 日报里新增“watchlist 命中”小节

---

## 文件设计

### 新建配置文件
- Create: `/home/ubuntu/.hermes/research-digest/config/watchlists.json`

建议初始结构：
```json
{
  "authors": {
    "manual": [],
    "auto_followed": []
  },
  "labs": {
    "manual": []
  },
  "venues": {
    "manual": []
  },
  "rules": {
    "author_boost": 8,
    "lab_boost": 6,
    "venue_boost": 5,
    "streak_boost_cap": 3
  }
}
```

### 新建状态文件
- Create: `/home/ubuntu/.hermes/research-digest/state/digest_state.json`

建议结构：
```json
{
  "health_history": [],
  "watch_hits": {
    "authors": {},
    "labs": {},
    "venues": {}
  },
  "last_run": null
}
```

### 可选新建辅助模块（推荐）
- Create: `/home/ubuntu/.hermes/scripts/research_digest_state.py`

职责：
- load/save watchlist
- load/save digest_state
- 规范化作者/venue 名称
- 计算 streak / hit_count
- 生成 health summary

### 修改前置抓取脚本
- Modify: `/home/ubuntu/.hermes/scripts/scholar_digest_input.py`

### 更新现有 cron 任务
- Modify runtime config: cron `6ac7b7bce4ce`

---

## 规则设计

### 1. Gmail 已关注作者自动导入规则

触发来源：
- Gmail Scholar 邮件主题：`<作者名> - 新文章`
- 备选兜底：邮件正文中的“因为您关注了 XXX 所著的新文章”

写入策略：
- 自动抽取作者名
- 写入 `watchlists.json -> authors.auto_followed`
- 记录：
  - `name`
  - `normalized_name`
  - `source = gmail_scholar_subject`
  - `first_seen`
  - `last_seen`
  - `last_message_subject`

去重策略：
- 小写规范化
- 去除多余空格
- 同名只更新 last_seen，不重复追加

### 2. 候选量告警阈值

建议阈值：
- 过少：combined < 3
- 正常：3 <= combined <= 25
- 过多：combined > 25

原因：
- 小于 3 通常意味着 Gmail/arXiv 至少一个源异常，或查询过窄。
- 大于 25 对日报粗读来说噪声偏高，应该明确提示“今日候选偏多，已截断精选”。

### 3. 健康状态分级

建议规则：
- `healthy`
  - Gmail 正常
  - arXiv 正常
  - combined >= 3
  - 正文获取率 >= 60%
- `degraded`
  - Gmail 无邮件但 arXiv 正常
  - 或正文获取率 30%-60%
  - 或候选过少/过多
- `failed`
  - Gmail 失败且 arXiv 失败
  - 或 combined = 0
  - 或正文获取率 < 30%

### 4. Watchlist 加权

建议权重：
- 命中 manual author：+8
- 命中 auto_followed author：+6
- 命中 lab：+6
- 命中 venue：+5
- 连续 2-3 次日报命中同一作者：额外 +1 到 +3（封顶 3）

排序原则：
先保留当前关键词分，再叠加 watchlist 分，不替代原有研究关键词相关性评分。

---

## 实施任务

### Task 1: 新建 watchlist 与 state 文件骨架

目标：让自动化第一次运行时就有稳定的配置/状态存储。

文件：
- Create: `/home/ubuntu/.hermes/research-digest/config/watchlists.json`
- Create: `/home/ubuntu/.hermes/research-digest/state/digest_state.json`

Step 1: 写最小 JSON 骨架

```json
{
  "authors": {"manual": [], "auto_followed": []},
  "labs": {"manual": []},
  "venues": {"manual": []},
  "rules": {"author_boost": 8, "lab_boost": 6, "venue_boost": 5, "streak_boost_cap": 3}
}
```

Step 2: 写空 state

```json
{
  "health_history": [],
  "watch_hits": {"authors": {}, "labs": {}, "venues": {}},
  "last_run": null
}
```

Step 3: 验证文件存在且可解析

Run:
```bash
python3 - <<'PY'
import json
for p in [
  '/home/ubuntu/.hermes/research-digest/config/watchlists.json',
  '/home/ubuntu/.hermes/research-digest/state/digest_state.json'
]:
    json.load(open(p))
    print('OK', p)
PY
```

Expected：两个文件均输出 OK。

---

### Task 2: 抽离状态辅助函数

目标：避免把 watchlist/health 逻辑全塞进主脚本。

文件：
- Create: `/home/ubuntu/.hermes/scripts/research_digest_state.py`
- Modify: `/home/ubuntu/.hermes/scripts/scholar_digest_input.py`

Step 1: 实现基础函数
- `normalize_name(text)`
- `load_watchlists()` / `save_watchlists()`
- `load_digest_state()` / `save_digest_state()`
- `upsert_auto_followed_author(name, subject, seen_at)`
- `record_watch_hit(kind, key, run_date)`

Step 2: 写一个最小 smoke test

Run:
```bash
python3 - <<'PY'
from research_digest_state import normalize_name
print(normalize_name(' Kai  Ni '))
PY
```

Expected：输出 `kai ni`

Step 3: 语法检查

Run:
```bash
python3 -m py_compile /home/ubuntu/.hermes/scripts/research_digest_state.py
```

Expected：无输出。

---

### Task 3: 把 Gmail 已关注作者自动导入 watchlist

目标：利用现有 Gmail Scholar 邮件主题，把“已关注作者”自动持久化。

文件：
- Modify: `/home/ubuntu/.hermes/scripts/scholar_digest_input.py`
- Modify: `/home/ubuntu/.hermes/scripts/research_digest_state.py`

Step 1: 从 `subject` 中抽 ` - 新文章` 前缀

示例：
```python
def extract_followed_author_from_subject(subject: str) -> str | None:
    m = re.match(r'\s*(.*?)\s*-\s*新文章\s*$', subject or '')
    return m.group(1).strip() if m else None
```

Step 2: 在 Gmail 扫描循环里调用 `upsert_auto_followed_author(...)`

Step 3: 把导入结果写入 payload

示例字段：
```json
"watchlist_import": {
  "auto_followed_authors_added": 1,
  "auto_followed_authors_total": 5
}
```

Step 4: 验证

Run:
```bash
/home/ubuntu/.hermes/hermes-agent/venv/bin/python3 /home/ubuntu/.hermes/scripts/scholar_digest_input.py > /tmp/digest.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/digest.json'))
print(p['watchlist_import'])
PY
```

Expected：看到自动导入统计，且 `watchlists.json` 里出现 Gmail 关注作者。

---

### Task 4: 产出健康状态 JSON

目标：把“失败告警/质量自检”从口头提示变成结构化状态。

文件：
- Modify: `/home/ubuntu/.hermes/scripts/scholar_digest_input.py`
- Modify: `/home/ubuntu/.hermes/scripts/research_digest_state.py`

Step 1: 计算数据源状态
- Gmail：`ok / no_messages / error / parse_failed`
- arXiv：`ok / zero_results / error`

Step 2: 计算候选量状态
- `too_few / normal / too_many`

Step 3: 计算回退标志
- `fallback_to_arxiv_only = True/False`

Step 4: 写入 payload

建议字段：
```json
"health": {
  "gmail_status": "ok",
  "arxiv_status": "ok",
  "gmail_message_count": 1,
  "gmail_candidate_count": 1,
  "arxiv_candidate_count": 12,
  "combined_candidate_count": 13,
  "candidate_volume_status": "normal",
  "fallback_to_arxiv_only": false,
  "overall_status": "healthy",
  "warnings": []
}
```

Step 5: 验证

Run:
```bash
/home/ubuntu/.hermes/hermes-agent/venv/bin/python3 /home/ubuntu/.hermes/scripts/scholar_digest_input.py > /tmp/digest.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/digest.json'))
print(json.dumps(p['health'], ensure_ascii=False, indent=2))
PY
```

Expected：health 块完整输出。

---

### Task 5: watchlist 命中加权与命中统计

目标：让作者/实验室/会议追踪真正影响排序，而不是只存个名单。

文件：
- Modify: `/home/ubuntu/.hermes/scripts/scholar_digest_input.py`
- Modify: `/home/ubuntu/.hermes/scripts/research_digest_state.py`

Step 1: 对候选论文做 watchlist match
- 作者命中：基于 `authors`
- 会议/期刊/arXiv category 命中：基于 `venue`
- 实验室命中：暂以作者 affiliation 缺失为前提，只预留字段，不硬上脆弱规则

Step 2: 在候选里增加字段

```json
"watchlist_matches": {
  "authors": ["Kai Ni"],
  "venues": ["cs.AR"],
  "labs": []
},
"watchlist_boost": 6
```

Step 3: 更新 `combined.sort(...)`，改成按 `score + watchlist_boost`

Step 4: 持久化命中次数/streak 到 `digest_state.json`

Step 5: 验证

Run:
```bash
/home/ubuntu/.hermes/hermes-agent/venv/bin/python3 /home/ubuntu/.hermes/scripts/scholar_digest_input.py > /tmp/digest.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/digest.json'))
for item in p['combined_candidates'][:5]:
    print(item['title'])
    print(item.get('watchlist_matches'), item.get('watchlist_boost'))
PY
```

Expected：至少 Gmail 关注作者相关论文应出现 author 命中或更高排序。

---

### Task 6: 更新 cron 晨报模板，展示健康状态和 watchlist 命中

目标：让用户在 Telegram 里直接看到“系统状态”和“watchlist 命中”，避免误判系统没抓到就是今天没论文。

文件：
- Modify runtime config: cron `6ac7b7bce4ce`

Step 1: 修改 prompt，要求它显式使用 `health` 和 `watchlist_import`

Step 2: 在日报里固定新增两块：
- `日报健康状态`
- `watchlist 命中`

推荐输出格式：
```text
日报健康状态
- Gmail：正常
- arXiv：正常
- 今日候选数：13
- 候选量告警：正常
- 正文获取率：5/6（83%）
- 是否回退为 arXiv-only：否
- 总体状态：healthy

watchlist 命中
- 自动导入 Gmail 已关注作者：Kai Ni（累计 1）
- 今日命中作者：Kai Ni
- 今日命中 venue：cs.AR
```

Step 3: 手动运行 cron 并检查消息内容

Run:
```bash
hermes cron run 6ac7b7bce4ce
```

Expected：Telegram/本地日报中出现健康状态和 watchlist 命中块。

---

### Task 7: 记录正文获取率

目标：把“正文抓取失败比例太高”变成可观测指标。

文件：
- Modify runtime config: cron `6ac7b7bce4ce`
- 可选 Modify: `/home/ubuntu/.hermes/research-digest/state/digest_state.json`

Step 1: 在 cron prompt 中要求统计：
- `fulltext_attempted`
- `fulltext_succeeded`
- `fulltext_failed`

Step 2: 要求它把这些值写入日报系统状态，并可选落盘到 `digest_state.json`

Step 3: 验证
- 人工检查今日晨报中是否出现 `正文获取率` 字段。

---

## 验证清单

实施完成前，必须全部通过：
- [ ] `scholar_digest_input.py` 能正常运行并输出 `health`
- [ ] `watchlists.json` 会自动出现 Gmail 已关注作者
- [ ] 候选论文里能看到 `watchlist_matches` / `watchlist_boost`
- [ ] 日报里能显式看到 Gmail / arXiv / 候选量 / 回退状态
- [ ] 日报里能显式看到正文获取率
- [ ] cron 手动触发一次后，Telegram 内容与本地归档格式一致
- [ ] 失败场景下（例如临时断 Gmail 或强制让 Gmail query 为空）能明确显示 degraded/fallback

---

## 推荐的实现顺序

1. Task 1-4：先把状态层做出来
2. Task 5：再把 watchlist 真正接入排序
3. Task 6-7：最后改 cron 展示层

原因：
- 先把状态做出来，问题最容易观测。
- 有了结构化状态，再调排序和 Telegram 输出不容易乱。

---

## 实施后的维护建议

- 每周人工看一次 `watchlists.json`，清理明显误导入的作者名。
- 如果后续真的要做实验室 tracking，再考虑引入 OpenAlex/Semantic Scholar affiliation；当前阶段先不要硬猜实验室，容易误匹配。
- 一旦日报里连续 3 天出现 `degraded`，应优先排查 Gmail API 或 arXiv query，而不是继续调提示词。
