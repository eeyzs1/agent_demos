---
name: a-share-research-enhance
description: >-
  Deepens A-share candidate judgment with valuation / quality / falsifier
  checklists (snapshot + relative value + risk). Use during 每日荐股终审, or when
  the user asks for 估值研判, 基本面质量, 贵不贵, undervalued, PE/PB context,
  or research enhancement on screened symbols. Does NOT replace dual-score
  screening; does NOT call Longbridge/vendor CLIs.
---

# A股投研增强（估值 + 质量 + 证伪）

你是**终审增强插件**，不是独立荐股引擎。

- **输入**：`agent_brief.json` 候选（含 `tech_score` / `news_score` / `fundamental` / `news[]`）
- **输出**：写回 `agent_judgments.json` 的 `research` 块 + 影响 `reasons`/`risks`/`confidence`
- **数据源**：仅本项目 brief / 本地行情与财务字段；**禁止**默认调用 Longbridge CLI 或其他券商终端

清单细节见 [checklist.md](checklist.md)。

## 何时加载

1. `a-share-daily-recommend` 终审步骤（默认对 Top 候选全量跑）
2. 用户单独问某票「贵不贵 / 估值 / 基本面质量」

## 工作流（嵌在终审内）

```
进度:
- [ ] 1. 读 brief 候选 + scores.fundamental
- [ ] 2. 按 checklist 填三维估值观 + 质量观 + 证伪条件
- [ ] 3. 映射到 reasons/risks/confidence/action_hint
- [ ] 4. 写入 judgments[].research
```

### Top vs 观察池

| 池 | 深度 |
|----|------|
| Top（综合分靠前，通常 ≤10） | 完整 checklist：估值三维 + 质量 + ≥1 证伪条件 |
| 观察池 | 轻量：估值一句话 + ≥1 risk；缺数据则标 `data_sparse` |

### 与双指标的关系

| 信号 | 用法 |
|------|------|
| `tech_score` | 时机/动量，**不能**单独定「低估」 |
| `news_score` + `news[]` | 近端催化/风险；标题与分数冲突时以标题为准 |
| `fundamentals.pe_ttm` / `pb` / `roe` | 估值与质量主证据；有数字必须引用 |
| `scores.fundamental` (0–1) | 质量/估值综合代理；作辅助，勿覆盖真实 PE/PB |
| `fundamentals.data_sparse` | `valuation_view = unknown`，**降低 confidence**，勿编造数字 |

### 硬约束

1. 不下单；措辞用「关注/观察」，禁止「稳赚/必涨/强烈买入」
2. 不把外部券商当默认数据源；有公开事实可用 WebSearch，并标注来源
3. 周期股（能源/化工/钢铁/航运/银行/地产）必须加周期 caveat——高 PE ≠ 机械看贵
4. 无 `fundamentals.pe_ttm`/`pb`/`roe` 时不写精确估值数字；有则必须引用
5. 每个 Top 候选至少 1 条 `VALUATION` 或 `QUALITY` reason/risk，以及 1 条 `falsifiers`

## 置信度微调（建议）

在双指标初判 confidence 上微调，夹在 0–100：

- 质量与估值同向支持 → +5～10
- `fundamental` 弱或新闻利空标题 → −10～20，倾向 `avoid` / 降档
- `data_sparse` → 最多 55，且不得给 `strong_watch`
