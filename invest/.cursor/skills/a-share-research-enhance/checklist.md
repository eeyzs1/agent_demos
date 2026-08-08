# 投研 Checklist（项目内适配版）

方法论吸收自公开投研实践（三维估值：当前快照 / 相对历史 / 行业位置；量化纪律：数据质量优先、风险调整、可证伪），**落地到本项目 brief 字段**，不依赖外部券商 CLI。

## A. 三维估值观 → `valuation_view`

对每个候选回答「贵不贵？」时，尽量覆盖三维；缺数据则降级，勿编造。

| 维度 | 理想证据 | 本项目可用代理 | 缺数据时 |
|------|----------|----------------|----------|
| 当前快照 | PE/PB/PS、股息率 | `fundamentals.pe_ttm` / `pb` / `ps`；辅以 `scores.fundamental` | `unknown` |
| 历史分位 | PE/PB 历史百分位 | 一般**不可用** → 勿声称「历史 N 分位」 | 跳过该维并注明 |
| 行业相对 | 相对行业中位数溢价/折价 | 同批候选间 PE/PB 对比；稀疏则不写排名 | `industry sample sparse` |

**合成标签**（写入 `research.valuation_view`）：

| 标签 | 含义 |
|------|------|
| `cheap` | PE/PB 相对同批偏低且质量不差，或基本面代理偏强且无强利空 |
| `fair` | 中性 |
| `expensive` | PE/PB 明显偏高，或技术过热 + 基本面弱 |
| `unknown` | `fundamentals.data_sparse` 或关键字段缺失 |

有真实 `pe_ttm`/`pb` 时**优先引用数字**（如「PE(TTM) 19.8」），禁止编造分位。

**周期股 caveat**（行业命中能源/化工/钢铁/航运/银行/地产等）：

> 周期行业 — PE 类信号需结合景气位置解读；勿机械「高PE=贵、低PE=便宜」。

写入 `research.caveats[]`。

## B. 质量观 → `quality_view`

用 brief 与新闻做**质量快检**（非完整尽调）：

| 检查项 | 偏强信号 | 偏弱信号 |
|--------|----------|----------|
| 盈利能力 | `roe` ≥ 15，或 `fundamental` ≥ 0.65 | `roe` ≤ 5，或 `fundamental` ≤ 0.40 |
| 增长/改善 | `revenue_yoy`/`net_profit_yoy` 明显为正；或新闻含预增/超预期 | 增长为负；或预亏/减值/处罚标题 |
| 治理/风险事件 | 无明显负面公告标题 | 诉讼、质押爆雷、退市风险、监管函 |
| 与技术背离 | 技术强但质量弱 → 降档，防追高 | 技术弱但质量强 → 可 `watch`，勿轻易 `strong_watch` |

标签：`strong` | `average` | `weak` | `unknown`

## C. 证伪条件 → `falsifiers[]`（必填 ≥1，Top 池）

每条用中文、可观察、尽量可在后续交易日验证，例如：

- 「若跌破近端均线且放量，关注逻辑失效」
- 「若出现减持/立案类标题，应降为 avoid」
- 「若基本面分持续低于 0.4 且无改善新闻，不再上调」

禁止空泛句（如「市场有风险」）。

## D. 映射到终审字段

| research 结论 | reasons/risks code | action / confidence |
|---------------|--------------------|---------------------|
| cheap + strong + 无重大利空 | `VALUATION` / `QUALITY` 作 reason | 可维持或上调；仍禁止「买入」措辞 |
| expensive 或 weak | 至少 1 条对应 risk | 倾向 `watch`→`avoid`，confidence −10～20 |
| unknown / data_sparse | risk code `DATA` | confidence ≤55；禁止 `strong_watch` |
| 消息标题与 news_score 冲突 | reason/risk 以标题为准，code `NEWS` | 按冲突方向调档 |

## E. `research` JSON 块（写入每条 judgment）

```json
{
  "valuation_view": "fair",
  "quality_view": "average",
  "data_sparse": false,
  "caveats": [],
  "falsifiers": ["若出现立案/减持标题则降为 avoid"],
  "notes": "fundamental=0.52，双指标中性偏技术"
}
```

## F. 量化纪律（防叙事过拟合）

1. **数据质量优先**：缺字段就降置信度，不补故事。
2. **风险调整**：高 `tech_score` + 弱质量 ≠ 高把握。
3. **可证伪**：没有 `falsifiers` 的 Top 研判视为未完成。
4. **研究与交易分离**：本 skill 只增强观察池逻辑，不触发下单。
