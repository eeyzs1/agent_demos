# A股智能分析与荐股 — 开发计划书

> 版本：v1.1  
> 日期：2026-08-07  
> 代码基线：`generated/automated-trading-system/`  
> 状态：**已确认开工**（见 §14 定案）

---

## 1. 目标与范围

### 1.1 用户最终目标（北极星）

1. **日常可用**：分析 A 股，给出可执行的股票推荐，并附带清晰理由与风险提示。  
2. **进阶目标**：在可控风险下辅助决策；后续再评估是否接入模拟盘/实盘自动化。  
3. **不做虚假承诺**：本计划不承诺「自动赚钱」。任何交易相关能力以**可验证证据**为准。

### 1.2 里程碑优先级

| 优先级 | 里程碑 | 用户可感知结果 |
|--------|--------|----------------|
| **P0（本期）** | **每日荐股报告（带理由）** | 每天一条命令 → 产出 Markdown/终端报告：Top N 股票 + 理由 + 风险 |
| P1 | 荐股质量与可追溯 | 因子可解释、历史跟踪、简单回测对照 |
| P2 | 端到端模拟盘闭环 | 报告 → 风控 → 纸面下单 → 持仓/盈亏 |
| P3 | 实盘接入（可选） | 真实券商（QMT/XTP 等），需单独安全评审 |

### 1.3 本期明确不做（Out of Scope）

- 实盘自动下单、保证收益、跟庄/内幕类信号  
- Web/移动端 UI、多用户账号体系  
- 分钟级/Tick 级高频交易  
- 用 mock 数据冒充真实行情验收

### 1.4 成功定义（P0 验收标准）

满足以下全部条件即视为「每日荐股报告（带理由）」达成：

1. **一条命令可跑通**：`python -m trading_system.cli.main recommend daily --top 10`（命令名可微调，但必须单一入口）。  
2. **报告含结构化字段**（每只股票至少）：代码、名称、综合分、分项分、**中文推荐理由（≥3 条）**、**风险提示（≥1 条）**、**建议置信度（0–100）**、适用场景、数据截至日期。  
3. **分析模式**：量化数据因子 + 新闻/公告摘要 → **LLM 综合研判**（API 凭据仅来自 `.env`，禁止写进仓库）。  
4. **数据真实**：行情/基本面/新闻来自 akshare（或明确配置的真实源），有本地缓存与失败降级说明。  
5. **可复现**：量化分数可复现；LLM 文案允许非确定性，但需落盘完整 prompt/response 快照（可脱敏）。  
6. **有证据**：样例报告落盘到 `output/reports/`，并有至少 1 次人工抽检记录。  
7. **运行方式**：支持手动 CLI + 定时调度脚本（Windows 任务计划 / cron）。  
8. **不假装交易**：本期只出建议，不下单。

---

## 2. 现状基线（基于代码审计）

### 2.1 可复用资产

| 模块 | 路径 | 现状 |
|------|------|------|
| 行情拉取 | `src/trading_system/data/fetcher.py` | akshare + parquet 缓存，可复用 |
| 多因子打分 | `src/trading_system/pipeline/screener.py` | 技术/基本面/资金/情绪权重已有 |
| 策略信号 | `src/trading_system/strategy/strategies.py` | 趋势/均值回归/突破 + 融合 |
| 风控规则 | `src/trading_system/risk/manager.py` | 仓位/止损/回撤/熔断逻辑存在 |
| 回测引擎 | `src/trading_system/backtest/engine.py` | 七指标 + MC + DSR，P1 可接 |
| CLI 骨架 | `src/trading_system/cli/main.py` | 命令多，但部分 API 断裂 |
| 配置 | `config/default.yaml` | 筛选权重、风控阈值可热配 |

### 2.2 阻塞 P0 的已知问题

1. CLI ↔ 领域模块接口不一致（如 `PaperExecutor` 不存在；research/sentiment 方法签名不匹配）。  
2. Screener 只输出分数，**没有自然语言理由生成层**。  
3. 新闻/公告分析需调用方喂入文章，**没有自动抓取与组装进报告**。  
4. 缺 `pyproject.toml` / 依赖锁定，安装与入口不清晰。  
5. `daily-run` 未形成「报告产物」契约（Markdown 落盘 + JSON sidecar）。  
6. 验收标准（task.yaml AC）全部 NOT_PROVEN，需用新的 P0 AC 对齐。

### 2.3 架构原则（全程遵守）

- 报告链路：**Data → Score → News → LLM Explain → Rank → Report**（先分析建议，交易后置）。  
- 展示层（CLI）零业务逻辑；LLM 调用封装在 `recommend/llm_client.py`。  
- 禁止生产路径 mock 行情；测试可用 fixture，但需标注。  
- LLM Key 只读环境变量 / `.env`，永不提交。  
- 所有关键决策写 audit_log。  
- 配置 YAML 可热更新（不重启进程改权重）。

---

## 3. 总体路线图

```
Phase 0  工程可运行基线          ── 3~5 人日
Phase 1  每日荐股报告（带理由） ── 8~12 人日   ← 第一目标交付
Phase 2  质量增强与跟踪         ── 5~8 人日
Phase 3  模拟盘闭环             ── 8~12 人日
Phase 4  实盘评估（可选）       ── 待定
```

建议节奏：每周一个可演示增量；Phase 1 结束必须能「每天自己看报告」。

---

## 4. Phase 0 — 工程可运行基线

**目标**：任意开发机能安装、导入、跑通最小命令，修复阻断 P0 的断裂点。

### Step 0.1 项目打包与依赖锁定

**做什么**

- 新增 `pyproject.toml`（或 `requirements.txt` + 可编辑安装）。  
- 声明依赖：`akshare`、`pandas`、`numpy`、`click`、`rich`、`pyyaml`、`pyarrow` 等。  
- 明确入口：`trading-system` console script → `trading_system.cli.main:cli`。

**完成标准**

- `pip install -e .` 成功。  
- `python -m trading_system.cli.main --help` 显示命令树。

**产出**：`pyproject.toml`、安装说明（可写进本目录 README 片段）。

---

### Step 0.2 CLI / 模块 API 对齐（阻断修复）

**做什么**

按优先级修复与 P0 相关的断裂（暂缓纯交易命令）：

| 问题 | 修复方向 |
|------|----------|
| `research.analyze(symbol)` 不存在 | 增加门面方法：拉公告/新闻 → `analyze_news` / `analyze_announcements` |
| `sentiment.analyze()` 无参调用 | CLI 先取市场宽度数据再传入；或提供 `analyze_market()` 封装 |
| `PaperExecutor` 缺失 | **P0 阶段**：交易命令标记 `not implemented` 或改挂 `ExecutionEngine`；不阻塞荐股 |
| `daily-run` 脆弱 | 重构为调用新的 `DailyRecommendPipeline`（Phase 1） |

**完成标准**

- `screener score`、`screener screen`、`data fetch` 三命令对真实数据可跑。  
- 失败时有明确错误信息，不抛未捕获 ImportError。

**产出**：修复 PR/变更集 + 简短手工验证记录。

---

### Step 0.3 配置与输出目录约定

**做什么**

- 在 `config/default.yaml` 增加 `recommend:` 段（见 Step 1.1）。  
- 固定目录：`output/reports/`、`output/snapshots/`、`data/cache/`。  
- `.gitignore` 覆盖 cache/reports（样例报告可提交 1 份到 `docs/examples/`）。

**完成标准**：空跑一次也能创建目录结构，不报权限错误。

---

### Step 0.4 冒烟测试最小集

**做什么**

- 新增 `tests/test_smoke_data_screener.py`：mock 网络或使用缓存 fixture，断言 screener 返回含 `total` 分。  
- CI 可选；本地 `pytest tests/test_smoke_*.py` 必过。

**完成标准**：冒烟测试绿。

**Phase 0 出口检查清单**

- [ ] 可安装  
- [ ] 数据拉取命令可用  
- [ ] 打分命令可用  
- [ ] 输出目录约定落地  
- [ ] 冒烟测试通过  

---

## 5. Phase 1 — 每日荐股报告（带理由）【第一交付目标】

**目标**：用户每天收盘后（或盘前）跑一条命令，得到「买什么 / 为什么 / 要注意什么」。

### 5.1 产品规格（报告长什么样）

#### 报告文件

- 路径：`output/reports/YYYY-MM-DD_daily_recommend.md`  
- 同步：`output/reports/YYYY-MM-DD_daily_recommend.json`（机器可读）

#### Markdown 报告结构（固定模板）

```markdown
# A股每日荐股报告 · YYYY-MM-DD

## 市场概况
- 指数表现 / 涨跌家数（若可得）
- 今日筛选宇宙规模、有效样本数
- 策略偏好简述（如：偏趋势 / 均衡）

## 今日推荐 Top N
### 1. 600519 贵州茅台 · 综合分 82.4 · 建议：观察/轻仓关注
**推荐理由**
1. ...
2. ...
3. ...
**分项得分**：技术 xx | 基本面 xx | 资金 xx | 情绪 xx
**主要风险**
- ...
**数据说明**：行情截至 ...；财务数据截至 ...

## 未入选但接近阈值（观察池）
...

## 免责声明
本报告仅供研究参考，不构成投资建议。
```

#### 单票 JSON schema（核心字段）

```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "as_of": "2026-08-07",
  "scores": {
    "technical": 78.0,
    "fundamental": 85.0,
    "capital_flow": 70.0,
    "sentiment": 60.0,
    "total": 82.4
  },
  "rank": 1,
  "action_hint": "watch",
  "reasons": [
    {"code": "TECH_TREND_UP", "text": "股价站上20/60日均线，趋势因子偏多", "weight": 0.4},
    {"code": "FUND_ROE_OK", "text": "近报告期盈利能力处于同业较高分位", "weight": 0.3}
  ],
  "risks": [
    {"code": "VALUATION_HIGH", "text": "估值分位偏高，追高风险大"}
  ],
  "confidence": 0.62,
  "data_refs": {"ohlcv": "...", "financials": "..."}
}
```

`action_hint` 枚举建议：`strong_watch` | `watch` | `avoid`（P0 不做自动「买入」措辞过强的话术）。

---

### Step 1.1 配置契约 `recommend`

**做什么**：在 `config/default.yaml` 增加：

```yaml
recommend:
  top_n: 10
  watchlist_n: 10
  universe: "all"          # all | hs300 | zz500 | custom
  custom_symbols: []
  min_total_score: 60
  min_listing_days: 60
  exclude_st: true
  reason_language: "zh-CN"
  max_reasons: 5
  max_risks: 3
  report_formats: ["markdown", "json"]
  schedule_hint: "15:30"   # 文档建议运行时间，非强制调度
```

**完成标准**：配置可加载；缺省值合理。

---

### Step 1.2 候选宇宙构建 `UniverseBuilder`

**做什么**

- 新模块：`src/trading_system/recommend/universe.py`。  
- 能力：全市场/指数成分/自定义列表；过滤 ST、次新、停牌（能力范围内）、无数据股票。  
- P0 可先支持：`custom` + `hs300`（成分从 akshare 拉）；`all` 做分页/上限（如最多 500 只，避免首日跑崩）。

**完成标准**

- 返回 `List[SymbolMeta]`（code, name, market, listing_date…）。  
- 审计：宇宙大小、过滤原因计数。

**工时参考**：1~1.5 人日。

---

### Step 1.3 打分服务封装 `ScoringService`

**做什么**

- 新模块：`src/trading_system/recommend/scoring.py`。  
- 对 Universe 批量调用现有 `StockScreener`，补齐失败重试与进度日志。  
- 输出标准化 `ScoredStock`（含分项分 + 原始因子字典，供解释层使用）。

**完成标准**

- 对 50 只股票批量打分成功（真实或缓存数据）。  
- 单票失败不拖垮整批。

**工时参考**：1 人日。

---

### Step 1.4 理由引擎 `ReasonEngine`（核心 · 定案为 LLM）

**做什么**

- 模块：`src/trading_system/recommend/reasons.py` + `llm_client.py`。  
- 输入：量化分项分 + 新闻标题列表。  
- 调用 OpenAI 兼容 Chat Completions（`.env`：`LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL`）。  
- 输出：reasons / risks / **confidence(0–100)** / action_hint / news_summary。  
- LLM 不可用时规则模板降级，报告标注 `llm_status: fallback`。  
- 可选落盘 prompt/response 到 `output/snapshots/`（脱敏，不含 API Key）。

**完成标准**

- 配置好 `.env` 后，Top 候选经 LLM 产出中文理由与置信度。  
- 无 Key 时仍可出完整报告（降级）。  
- 单元测试覆盖规则降级路径。

---

### Step 1.5 新闻/公告增强（可选但建议做薄）

**做什么**

- `src/trading_system/recommend/catalysts.py`。  
- 对 Top N（不是全宇宙）尝试拉取近期公告标题；用现有 `ResearchAnalyzer` 做关键词情感。  
- 成功则追加 1 条 catalyst 理由；失败则跳过并在报告「数据缺口」注明。

**完成标准**：有/无新闻都能出完整报告；有新闻时理由更丰满。

**工时参考**：1~2 人日。

---

### Step 1.6 排序与动作建议 `Ranker`

**做什么**

- `src/trading_system/recommend/ranker.py`。  
- 按 `total` 分排序；可选二次过滤（波动过大、单日涨幅过大追高惩罚）。  
- 映射 `action_hint`：高分+低风险 → `strong_watch`；中等 → `watch`；风险规则触发 → 移入观察或 `avoid`。

**完成标准**：排序稳定；惩罚规则有配置开关。

**工时参考**：0.5~1 人日。

---

### Step 1.7 报告渲染 `ReportWriter`

**做什么**

- `src/trading_system/recommend/report.py`。  
- 渲染 Markdown + JSON；写入 `output/reports/`。  
- CLI Rich 终端摘要（表格：代码/名称/总分/一句话理由）。

**完成标准**：打开 Markdown 文件可读；JSON 可被后续程序解析。

**工时参考**：1 人日。

---

### Step 1.8 流水线编排 `DailyRecommendPipeline`

**做什么**

- `src/trading_system/recommend/pipeline.py`。  
- 编排：Universe → Score → Reason → Rank → Report。  
- 写 snapshot：`output/snapshots/YYYY-MM-DD/`（打分中间表 parquet/json）。  
- audit_log：开始/结束/Top N 列表/耗时/失败计数。

**完成标准**：纯 Python API `run_daily_recommend(as_of=None) -> ReportPaths` 可调用。

**工时参考**：1 人日。

---

### Step 1.9 CLI 入口

**做什么**

- 新增命令组：

```text
recommend daily [--top N] [--universe hs300|all|custom] [--as-of YYYY-MM-DD] [--format md|json|both]
recommend show --date YYYY-MM-DD
recommend explain --symbol 600519
```

- 废弃或改道旧的半残 `daily-run`：内部转调新 pipeline，或打印迁移提示。

**完成标准**：文档中的「一条命令」真实可用。

**工时参考**：0.5~1 人日。

---

### Step 1.10 P0 验收与样例

**做什么**

1. 用 `hs300` 宇宙跑通一次，保存样例到 `docs/examples/sample_daily_recommend.md`。  
2. 人工抽检 Top 5：理由是否与分数逻辑一致、有无胡编。  
3. 测试：  
   - `tests/test_reason_engine.py`（规则确定性）  
   - `tests/test_daily_recommend_pipeline.py`（用 fixture 数据 E2E）  
4. 更新 `task.yaml` / session-state：新增并勾验 P0 AC（或单独 `docs/验收记录-P0.md`）。

**完成标准**：第 1.4 节六条成功定义全部打勾。

**Phase 1 出口检查清单**

- [ ] `recommend daily` 一条命令出报告  
- [ ] 每只股票有中文理由与风险  
- [ ] MD + JSON 落盘  
- [ ] 样例报告入库  
- [ ] ReasonEngine 单测通过  
- [ ] 抽检记录存在  

---

## 6. Phase 2 — 荐股质量与可追溯（巩固「分析 A 股」）

**目标**：让推荐「经得起回头看」，而不只是当天好看。

### Step 2.1 推荐台账

- 表/文件：`output/ledger/recommendations.parquet`。  
- 字段：date, symbol, rank, score, action_hint, reasons_codes。  
- 命令：`recommend history --symbol` / `recommend ledger --from --to`。

### Step 2.2 事后追踪（朴素版）

- T+1/T+5/T+20 收益相对基准（默认沪深300）。  
- 周报：命中率、平均超额、最大回撤（组合等权简化）。  
- **完成标准**：连续跑 20 个交易日有自动统计（可先历史回放）。

### Step 2.3 解释性增强

- `recommend explain --symbol`：打印因子雷达与触发规则清单。  
- 可选：把策略融合信号（趋势/回归/突破）并入理由。

### Step 2.4 轻量回测挂钩

- 用现有 backtest：对「每日 Top10 持有 N 日」做简单策略回测。  
- 输出是否显著跑赢基准（DSR 可选）。  
- **注意**：回测好 ≠ 未来赚；报告中必须写清。

### Step 2.5 调度

- **已前移到 P0**：`scripts/schedule-daily-recommend.ps1`（手动跑 / `-Register` 注册工作日 15:35）。  
- 失败时依赖任务计划历史与报告目录是否生成文件判断。

**Phase 2 出口**：有历史台账 + 至少一份「近 N 日推荐表现」报告。

---

## 7. Phase 3 — 模拟盘闭环（朝「自动执行」迈步，仍不承诺赚钱）

**前置**：Phase 1 稳定、Phase 2 至少有基础追踪。

### Step 3.1 修复纸面执行

- 统一 `ExecutionEngine` API；去掉错误的 `PaperExecutor` 引用。  
- 持久化：订单、成交、持仓、现金（SQLite 或 parquet）。  
- 真实用最新价/次日开盘价规则（配置化），禁止硬编码 `price=10.0`。

### Step 3.2 风控闸门接入报告

- 报告中的候选 → `RiskManager` 仓位与止损校验 → 生成「建议委托清单」。  
- 命令：`trade plan-from-report --date` → `trade paper-submit --dry-run|--confirm`。

### Step 3.3 日终对账

- 持仓市值、当日盈亏、回撤、是否触发熔断。  
- 与 audit_log 一致。

### Step 3.4 验收（对齐原 AC 子集）

- Paper 默认；无 `--live` 不能进 live 模式。  
- 止损强制；日亏/回撤熔断可测。

**Phase 3 出口**：报告驱动的纸面交易闭环可演示。

---

## 8. Phase 4 — 实盘（可选，单独立项）

仅当同时满足：

1. 纸面运行 ≥ 约定周数且风控无严重事故；  
2. 选定券商 API（QMT/XTP 等）并完成账号安全方案；  
3. 用户书面确认风险与资金上限。

步骤概要：BrokerAdapter → 只读查询 → 小额下单 → 全量开关。  
本计划书不展开实现细节，避免范围膨胀。

---

## 9. 模块落地结构（建议）

```text
src/trading_system/recommend/
  __init__.py
  universe.py      # Step 1.2
  scoring.py       # Step 1.3
  reasons.py       # Step 1.4
  catalysts.py     # Step 1.5
  ranker.py        # Step 1.6
  report.py        # Step 1.7
  pipeline.py      # Step 1.8
  models.py        # dataclass / TypedDict
```

依赖方向（允许）：

```text
recommend → data, pipeline(screener), strategy?, research?, sentiment?, core
recommend ✗→ execution（P0 禁止依赖交易，避免耦合）
```

---

## 10. 测试与质量门禁

| 层级 | 内容 | 何时 |
|------|------|------|
| 单元 | ReasonEngine 规则表 | Phase 1 |
| 集成 | Pipeline + fixture OHLCV | Phase 1 |
| 手工 | 真实 akshare 日跑样例 | Phase 1 出口 |
| 回归 | 台账字段不破坏 | Phase 2 |
| 风控 | 熔断/止损单测 | Phase 3 |

门禁口号：**没有落盘报告 + 测试，不算完成。**

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| akshare 限流/接口变更 | 日跑失败 | 缓存、重试、缩小宇宙、失败报告 |
| 理由模板生硬/不准 | 用户不信任 | 规则可配置；抽检；后续再考虑 LLM 润色（需人工复核开关） |
| 全市场打分太慢 | 体验差 | P0 默认 hs300；并发/缓存；增量更新 |
| 「推荐」被当成稳赚 | 预期错位 | 报告强制免责声明；action_hint 避免「立即买入」 |
| 范围漂到实盘 | 延期 | 严格按 Phase 门禁；P0 不碰 broker |

---

## 12. 建议排期（单人全职估算）

| 阶段 | 人日 | 累计 |
|------|------|------|
| Phase 0 | 3~5 | 3~5 |
| Phase 1（第一目标） | 8~12 | **11~17** |
| Phase 2 | 5~8 | 16~25 |
| Phase 3 | 8~12 | 24~37 |
| Phase 4 | 另估 | — |

若每天只有部分时间投入，按日历周 ≈ 人日 × 1.5~2。

---

## 13. 立即开始的第一周任务拆解（可直接派工）

**Day 1**

- [ ] Step 0.1 打包安装  
- [ ] Step 0.3 目录与 `recommend` 配置段  

**Day 2**

- [ ] Step 0.2 修复 `data` / `screener` 相关断裂  
- [ ] Step 0.4 冒烟测试  

**Day 3**

- [ ] Step 1.2 UniverseBuilder（先 hs300）  
- [ ] Step 1.3 ScoringService  

**Day 4–5**

- [ ] Step 1.4 ReasonEngine + 单测  
- [ ] Step 1.6 Ranker  

**Day 6**

- [ ] Step 1.7 ReportWriter  
- [ ] Step 1.8 Pipeline  

**Day 7**

- [ ] Step 1.9 CLI  
- [ ] Step 1.10 真实跑通 + 样例报告 + 抽检  

→ **周末演示：给你一份「今日荐股报告」。**

---

## 14. 决策定案（用户确认 · 2026-08-07）

| # | 议题 | 定案 |
|---|------|------|
| 1 | 股票池 | **A股主板**（沪：600/601/603；深：000/001/002）。排除创业板(300/301)、科创板(688)、北交所等 |
| 2 | 推荐数量 | **Top 10 + 观察池 10** |
| 3 | 理由生成 | **数据分析 + 新闻 → 终审 LLM**。默认终审 = **Cursor Agent**（skill `a-share-daily-recommend`）；可选 `.env` 外部 API |
| 4 | 措辞 | 「关注/观察」+ **建议置信度（0–100）**；避免「强烈买入」 |
| 5 | 运行方式 | **手动命令 + 定时调度都做**；Agent 终审在 Cursor 内触发 skill |
| 6 | 交易 | **先给建议，交易后置**（模拟盘/实盘不进本期） |

Skill 路径：`.cursor/skills/a-share-daily-recommend/`  
脚本：`prepare_agent_brief.py` →（Agent 写 judgments）→ `finalize_from_judgments.py`

按 **Phase 0 → Phase 1** 执行；本文为任务拆解与验收依据。

---

## 15. 文档维护

| 文件 | 用途 |
|------|------|
| `docs/开发计划书-A股每日荐股.md` | 本文，范围与步骤 SSOT |
| `docs/examples/sample_daily_recommend.md` | P0 样例报告（待生成） |
| `docs/验收记录-P0.md` | 验收证据（待写） |
| `config/default.yaml` → `recommend` | 运行参数 |

变更流程：若调整范围，先改本计划书版本号（v1.1…），再改代码，避免再次任务漂移。
