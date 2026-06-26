# Agent 设计模式文档集

本仓库系统性地整理了 **12 大类、110 种** Agent 设计模式，每种模式均配有概念说明、核心流程图和完整的 Python 示例代码。

> 📖 **不知道该选哪个模式？** 请先阅读 [**场景适配指南**](docs/场景适配指南.md) — 包含快速选型决策树、10 个典型场景详解、8 大行业方案、8 个经典组合配方。

## 🆕 最近更新

**第三轮 2025-2026 内容更新**（104 → 110）：新增 6 种 2025-2026 前沿模式。
- 自主规划：Durable Execution（持久化执行引擎）
- 检索增强：Agentic RAG（代理式 RAG）、CAG（缓存增强生成）、Multimodal RAG（多模态 RAG）、Reranking（重排序）
- 框架范式：Subagents（子代理模式）

**第二轮 2025-2026 内容更新**（100 → 104）：新增 4 种 2026 年前沿模式。
- 记忆管理：Dreaming（梦境记忆整合，OpenAI 2026.06）
- 框架范式：Context Engineering / Compaction（上下文工程）
- 自主规划：Long-running Agents（长时运行 Agent）
- 工具使用：Code-as-Action（代码即行动）

**2025-2026 年内容更新**（93 → 100）：新增 7 种设计模式，行业方案新增"软件研发"。
- 自主规划：Agentic Coding（自主编程）
- 检索增强：LightRAG（轻量图谱检索）
- 记忆管理：Mem0（记忆即数据库）
- 框架范式：Orchestrator-Workers（总调度）、Evaluator-Optimizer（评估优化）
- 工具使用：Browser Use / Web Agent（浏览器Agent）
- 成本优化：Speculative Decoding（推测解码）

**文档一致性全面加固**：
- 场景适配指南矩阵表补充 28 个缺失模式，覆盖率从 70% 提升至 100%
- 各章总结对比表同步补充新增模式（02/03/04/05/12 章）
- 02 章 2.9 Agentic Coding 重组到正确位置（总结表之前）
- 12 章定价表扩展到 18 个 2025-2026 主流模型

**新增 10 种设计模式**（83 → 93）：
- 推理增强：Test-Time Compute Scaling (o1)、Chain-of-Verification
- 检索增强：Speculative RAG、Adaptive RAG
- 多智能体协作：A2A Protocol
- 记忆管理：Letta (MemGPT 演进)
- 安全对齐：DPO & RLAIF、Llama Guard
- 工具使用：Structured Outputs
- 成本优化：Prompt Caching & Batch API

**新增 4 个行业方案**（4 → 8）：教育、法律、制造、软件研发

**代码质量全面加固**：
- 全部示例代码添加 `content or ""` None 防护和 `json.loads` try/except 兜底
- PoT / CRITIC 的 `exec()` 改为 `SAFE_BUILTINS` 白名单沙箱
- 修复 GoT 多父节点追溯、Swarm 贪婪正则、CrewAI 上下文累加等逻辑 bug
- 修正 Self-RAG 流程图、MemGPT 记忆归类、Generative Agents 衰减系数等技术错误

## 📚 文档目录

| 序号 | 类别 | 模式数量 | 文档 |
|:---:|------|:------:|------|
| 01 | 推理增强类 | 15 | [01_推理增强类.md](docs/01_推理增强类.md) |
| 02 | 自主规划与执行类 | 11 | [02_自主规划与执行类.md](docs/02_自主规划与执行类.md) |
| 03 | 检索增强类 (RAG) | 16 | [03_检索增强类.md](docs/03_检索增强类.md) |
| 04 | 多智能体协作类 | 9 | [04_多智能体协作类.md](docs/04_多智能体协作类.md) |
| 05 | 记忆与状态管理类 | 8 | [05_记忆与状态管理类.md](docs/05_记忆与状态管理类.md) |
| 06 | 框架与编程范式类 | 12 | [06_框架与编程范式类.md](docs/06_框架与编程范式类.md) |
| 07 | 安全与对齐类 | 10 | [07_安全与对齐类.md](docs/07_安全与对齐类.md) |
| 08 | 工具使用与函数调用类 | 10 | [08_工具使用与函数调用类.md](docs/08_工具使用与函数调用类.md) |
| 09 | 自我纠错与迭代改进类 | 5 | [09_自我纠错与迭代改进类.md](docs/09_自我纠错与迭代改进类.md) |
| 10 | 人机协作类 | 4 | [10_人机协作类.md](docs/10_人机协作类.md) |
| 11 | 评估与测试类 | 4 | [11_评估与测试类.md](docs/11_评估与测试类.md) |
| 12 | 可观测性与成本优化类 | 6 | [12_可观测性与成本优化类.md](docs/12_可观测性与成本优化类.md) |
| — | **场景适配指南** | — | [场景适配指南.md](docs/场景适配指南.md) |
| — | 🏯 模式江湖（趣味图鉴） | 110 | [模式江湖.md](docs/模式江湖.md) |
| — | 🛒 电商/零售行业方案 | 3 | [行业方案_电商零售.md](docs/行业方案_电商零售.md) |
| — | 🏦 金融行业方案 | 3 | [行业方案_金融.md](docs/行业方案_金融.md) |
| — | 💼 SaaS/企业服务行业方案 | 3 | [行业方案_SaaS企业服务.md](docs/行业方案_SaaS企业服务.md) |
| — | 🏥 医疗健康行业方案 | 3 | [行业方案_医疗健康.md](docs/行业方案_医疗健康.md) |
| — | 🎓 教育行业方案 | 3 | [行业方案_教育.md](docs/行业方案_教育.md) |
| — | ⚖️ 法律行业方案 | 3 | [行业方案_法律.md](docs/行业方案_法律.md) |
| — | 🏭 制造行业方案 | 3 | [行业方案_制造.md](docs/行业方案_制造.md) |
| — | 💻 软件研发行业方案 | 4 | [行业方案_软件研发.md](docs/行业方案_软件研发.md) |

## 🗺️ 模式全景图

```
Agent 设计模式
├── 推理增强类 — 让模型"想清楚再回答"
│   ├── CoT (思维链)          ├── ToT (思维树)
│   ├── GoT (思维图)          ├── Self-Consistency (自洽性)
│   ├── PoT (程序化思维)      ├── Step-Back (退一步提示)
│   ├── Least-to-Most (从易到难)  ├── Analog Prompting (类比提示)
│   ├── SoT (骨架思维)        ├── RE2 (重复阅读)
│   ├── S2A (系统2注意力)     ├── Emotion Prompting (情感提示)
│   ├── LATS (语言智能体树搜索)
│   ├── Test-Time Compute Scaling (测试时计算扩展/o1)
│   └── Chain-of-Verification (验证链/CoV)
│
├── 自主规划与执行类 — 让Agent自主制定计划并执行
│   ├── AutoGPT / BabyAGI     ├── HuggingGPT / TaskMatrix
│   ├── DEPS                  ├── ART
│   ├── ADaPT                 ├── Plan-and-Solve (计划与求解)
│   ├── LLM+P (LLM+经典规划器) ├── ReWOO (推理与观察解耦)
│   ├── Agentic Coding (自主编程)
│   ├── Long-running Agents (长时运行Agent)
│   └── Durable Execution (持久化执行引擎)
│
├── 检索增强类 (RAG) — 何时检索、检索什么、如何利用
│   ├── Standard RAG          ├── Self-RAG
│   ├── Corrective RAG        ├── RAISE
│   ├── Active RAG            ├── GraphRAG (知识图谱RAG)
│   ├── HyDE (假设文档嵌入)   ├── Self-Ask (自问自答)
│   ├── FLARE (前瞻式主动检索)
│   ├── Speculative RAG (推测式RAG)
│   ├── Adaptive RAG (自适应RAG)
│   ├── LightRAG (轻量图谱检索)
│   ├── Agentic RAG (代理式RAG)
│   ├── CAG (缓存增强生成)
│   ├── Multimodal RAG (多模态RAG)
│   └── Reranking (重排序)
│
├── 多智能体协作类 — 多Agent交互获得更高质量产出
│   ├── AutoGen               ├── MetaGPT
│   ├── CrewAI                ├── MoA (混合Agent)
│   ├── MAD (多Agent辩论)     ├── DyLAN (动态Agent网络)
│   ├── OpenAI Swarm (轻量编排) ├── ChatDev (聊天驱动开发)
│   └── A2A Protocol (Agent间通信协议)
│
├── 记忆与状态管理类 — 让Agent"记住该记住的、忘掉该忘掉的"
│   ├── MemGPT                ├── Generative Agents
│   ├── Reflection-based Memory   ├── RAG-based Memory
│   ├── Episodic Memory (情景记忆)
│   ├── Letta (MemGPT演进/有状态Agent)
│   ├── Mem0 (记忆即数据库)
│   └── Dreaming (梦境记忆整合)
│
├── 框架与编程范式类 — 从系统架构层面组织LLM调用
│   ├── DSPy                  ├── Flow Engineering (LangGraph)
│   ├── Map-Reduce Pattern    ├── Router / MoE
│   ├── Structured Output     ├── MCP (模型上下文协议)
│   ├── Semantic Kernel       ├── Prompt Chaining (提示链)
│   ├── Orchestrator-Workers (总调度)
│   ├── Evaluator-Optimizer (评估优化)
│   ├── Context Engineering / Compaction (上下文工程)
│   └── Subagents (子代理模式)
│
├── 安全与对齐类 — 确保Agent输出安全、合规、符合价值观
│   ├── Constitutional AI     ├── Guardrails / NeMo-Guardrails
│   ├── LLM-as-a-Judge       ├── Self-Alignment
│   ├── RLHF-aware Design     ├── Red Teaming (红队测试)
│   ├── Prompt Injection Defense  ├── Jailbreak Defense
│   ├── DPO & RLAIF (直接偏好优化与AI反馈对齐)
│   └── Llama Guard (输入输出安全分类)
│
├── 工具使用与函数调用类 — Agent区别于普通LLM的核心能力
│   ├── ReAct                 ├── Function Calling
│   ├── Toolformer            ├── Code Interpreter
│   ├── API Agent / Web Agent ├── Computer Use / GUI Agent
│   ├── Parallel Function Calling
│   ├── Structured Outputs (结构化输出)
│   ├── Browser Use / Web Agent (浏览器Agent)
│   └── Code-as-Action (代码即行动)
│
├── 自我纠错与迭代改进类 — 从"能用"到"可靠"的关键
│   ├── Self-Refine           ├── Reflexion
│   ├── CRITIC                ├── Iterative Refinement
│   └── Self-Discover (自我发现推理结构)
│
├── 人机协作类 — 生产系统的必备机制
│   ├── Human-in-the-Loop     ├── Interactive Agent
│   ├── Cobots                └── Supervised Autonomy
│
├── 评估与测试类 — 让Agent质量可衡量、可验证
│   ├── LLM-as-a-Judge        ├── Pairwise Comparison
│   ├── Trajectory Evaluation └── Adversarial Testing
│
└── 可观测性与成本优化类 — 生产环境的"看得见、控得住、省得了"
    ├── Tracing & Logging     ├── Token & Cost Monitoring
    ├── Caching & Memoization ├── Model Routing & Cascading
    ├── Prompt Caching & Batch API (提示缓存与批量API)
    └── Speculative Decoding (推测解码)
```

## 📖 推荐阅读顺序

> 💡 **第一步永远是** [场景适配指南](docs/场景适配指南.md) — 用决策树 30 秒找到你需要的模式。

### 入门路径（先理解核心概念）
1. **08 工具使用与函数调用类** → 理解 Agent 的核心能力（ReAct 是基石）
2. **01 推理增强类** → 理解如何增强 LLM 的推理能力
3. **09 自我纠错与迭代改进类** → 理解如何让 Agent 变得可靠

### 进阶路径（构建完整 Agent）
4. **02 自主规划与执行类** → 理解 Agent 的自主性
5. **05 记忆与状态管理类** → 理解 Agent 的记忆体系
6. **03 检索增强类** → 理解知识增强机制

### 高级路径（系统级设计）
7. **04 多智能体协作类** → 理解多 Agent 协作
8. **06 框架与编程范式类** → 理解工程化方法
9. **07 安全与对齐类** → 理解安全保障
10. **10 人机协作类** → 理解生产环境部署

### 生产路径（上线与运维）
11. **11 评估与测试类** → 理解如何评估和验证 Agent 质量
12. **12 可观测性与成本优化类** → 理解生产环境的监控与成本控制

## ⚙️ 环境配置

**Python 3.10+**，所有示例代码基于 OpenAI Python SDK：

```bash
pip install openai numpy
```

设置环境变量：

```bash
export OPENAI_API_KEY="your-api-key"
# 如使用兼容接口（如 Azure OpenAI、本地部署），还需设置：
export OPENAI_BASE_URL="https://your-api-endpoint"
```

部分模式需要额外依赖：
- AutoGen 示例：`pip install pyautogen`
- 向量检索示例：内置 `SimpleVectorStore`，无需额外安装
- 语义缓存示例（12.3）：依赖 `numpy`（已包含在基础安装中）
- 链路追踪示例（12.1）：可选集成 OpenTelemetry 用于生产环境
- 生产环境重试：推荐 `pip install tenacity`（指数退避重试）

> ⚠️ **生产环境注意事项**：本文档中的示例代码为教学目的编写，省略了生产环境必需的错误处理（如 API 限流重试、超时处理、网络异常恢复等）。生产部署时请务必：
> - 对所有 LLM 调用添加 `try/except`，捕获 `openai.RateLimitError`、`openai.APIError`、`openai.APITimeoutError` 等
> - 实现指数退避重试机制（推荐使用 `tenacity` 库）
> - 对 `response.choices[0].message.content` 做 None 防护（`content or ""`）
> - 对 `json.loads` 做 try/except 兜底，处理 LLM 返回非标准 JSON 的情况
> - 代码执行类模式（PoT、CRITIC 等）的沙箱仅做演示，生产环境请使用 Docker 容器或专用沙箱服务

## 📐 文档结构约定

每个模式的文档遵循统一结构：

```
模式名称
├── 概念说明        — 通俗解释 + 类比理解
├── 核心流程/原理   — Mermaid 流程图 + 关键步骤说明
├── 完整示例代码    — 基于 OpenAI API 的可运行 Python 代码
│   ├── 环境配置
│   ├── 核心类实现
│   └── 主流程演示
├── 代码要点说明    — 关键方法与对应阶段
└── 总结对比表      — 多维度横向对比 + 选型建议
```
