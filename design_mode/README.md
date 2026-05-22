# Agent 设计模式文档集

本仓库系统性地整理了 **10 大类、51 种** Agent 设计模式，每种模式均配有概念说明、核心流程图和完整的 Python 示例代码。

## 📚 文档目录

| 序号 | 类别 | 模式数量 | 文档 |
|:---:|------|:------:|------|
| 01 | 推理增强类 | 8 | [01_推理增强类.md](docs/01_推理增强类.md) |
| 02 | 自主规划与执行类 | 5 | [02_自主规划与执行类.md](docs/02_自主规划与执行类.md) |
| 03 | 检索增强类 (RAG) | 5 | [03_检索增强类.md](docs/03_检索增强类.md) |
| 04 | 多智能体协作类 | 6 | [04_多智能体协作类.md](docs/04_多智能体协作类.md) |
| 05 | 记忆与状态管理类 | 4 | [05_记忆与状态管理类.md](docs/05_记忆与状态管理类.md) |
| 06 | 框架与编程范式类 | 5 | [06_框架与编程范式类.md](docs/06_框架与编程范式类.md) |
| 07 | 安全与对齐类 | 5 | [07_安全与对齐类.md](docs/07_安全与对齐类.md) |
| 08 | 工具使用与函数调用类 | 5 | [08_工具使用与函数调用类.md](docs/08_工具使用与函数调用类.md) |
| 09 | 自我纠错与迭代改进类 | 4 | [09_自我纠错与迭代改进类.md](docs/09_自我纠错与迭代改进类.md) |
| 10 | 人机协作类 | 4 | [10_人机协作类.md](docs/10_人机协作类.md) |

## 🗺️ 模式全景图

```
Agent 设计模式
├── 推理增强类 — 让模型"想清楚再回答"
│   ├── CoT (思维链)          ├── ToT (思维树)
│   ├── GoT (思维图)          ├── Self-Consistency (自洽性)
│   ├── PoT (程序化思维)      ├── Step-Back (退一步提示)
│   ├── Least-to-Most (从易到难)  └── Analog Prompting (类比提示)
│
├── 自主规划与执行类 — 让Agent自主制定计划并执行
│   ├── AutoGPT / BabyAGI     ├── HuggingGPT / TaskMatrix
│   ├── DEPS                  ├── ART
│   └── ADaPT
│
├── 检索增强类 (RAG) — 何时检索、检索什么、如何利用
│   ├── Standard RAG          ├── Self-RAG
│   ├── Corrective RAG        ├── RAISE
│   └── Active RAG
│
├── 多智能体协作类 — 多Agent交互获得更高质量产出
│   ├── AutoGen               ├── MetaGPT
│   ├── CrewAI                ├── MoA (混合Agent)
│   ├── MAD (多Agent辩论)     └── DyLAN (动态Agent网络)
│
├── 记忆与状态管理类 — 让Agent"记住该记住的、忘掉该忘掉的"
│   ├── MemGPT                ├── Generative Agents
│   ├── Reflection-based Memory   └── RAG-based Memory
│
├── 框架与编程范式类 — 从系统架构层面组织LLM调用
│   ├── DSPy                  ├── Flow Engineering (LangGraph)
│   ├── Map-Reduce Pattern    ├── Router / MoE
│   └── Structured Output
│
├── 安全与对齐类 — 确保Agent输出安全、合规、符合价值观
│   ├── Constitutional AI     ├── Guardrails / NeMo-Guardrails
│   ├── LLM-as-a-Judge       ├── Self-Alignment
│   └── RLHF-aware Design
│
├── 工具使用与函数调用类 — Agent区别于普通LLM的核心能力
│   ├── ReAct                 ├── Function Calling
│   ├── Toolformer            ├── Code Interpreter
│   └── API Agent / Web Agent
│
├── 自我纠错与迭代改进类 — 从"能用"到"可靠"的关键
│   ├── Self-Refine           ├── Reflexion
│   ├── CRITIC                └── Iterative Refinement
│
└── 人机协作类 — 生产系统的必备机制
    ├── Human-in-the-Loop     ├── Interactive Agent
    ├── Cobots                └── Supervised Autonomy
```

## 📖 推荐阅读顺序

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

## ⚙️ 环境配置

所有示例代码基于 OpenAI Python SDK：

```bash
pip install openai numpy
```

设置环境变量：

```bash
export OPENAI_API_KEY="your-api-key"
# 如使用兼容接口，还需设置：
export OPENAI_BASE_URL="https://your-api-endpoint"
```

部分模式需要额外依赖：
- AutoGen 示例：`pip install pyautogen`
- 向量检索示例：内置 `SimpleVectorStore`，无需额外安装

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
