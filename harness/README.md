# Harness Engineering Framework

> 你只需要说出你想要什么，剩下的交给系统。

[English version](README_EN.md)

## 这是什么？

想象一下：你有一个想法，但不知道怎么实现。你告诉这个系统"我需要一个客户入驻系统"，它会：

1. **理解你的想法** — 把模糊的需求翻译成清晰的任务定义
2. **设计工作方式** — 自动生成规则、流程、检查点
3. **分配专业角色** — 自动创建一组 AI 代理，各司其职
4. **编排执行** — 规划谁先做、谁后做、谁并行做
5. **验证结果** — 自动检查产出是否达标
6. **越用越聪明** — 每次犯错都会让系统变得更好

**一句话**：这是一个"AI 代理的管理系统"——它确保 AI 代理干活靠谱，而不是瞎搞。

---

## 我该怎么用？

### 如果你不是程序员

你不需要懂代码。你只需要在 AI 编程工具（比如 Trae、Cursor、Claude Code）中打开这个项目，然后告诉它你想做什么。

**示例——你只需要说：**

- "我需要一个客户入驻系统"
- "帮我做一个竞品价格监控工具"
- "我想自动化每周报告的生成"
- "做一个自由职业者发票管理的 SaaS"

AI 会自动读取这个项目的规则，然后：
- 解析你的需求
- 生成适合这个任务的约束和工作流
- 创建专门的代理来执行
- 验证结果是否达标

**你需要做的只有两件事：**
1. **说出你想要什么**（越模糊越好，系统会帮你理清）
2. **确认假设**（系统会列出它做的假设，你只需确认或纠正）

### 如果你是软件工程师

这个项目是一个 **自举的元 Harness**——它不是给某个项目用的 harness，而是**生成 harness 的 harness**。

**核心公式：**
```
Agent = Model + Harness
```
- Model 提供智能
- Harness 让智能可靠地发挥作用
- **更好的 Harness 往往比更好的 Model 更重要**

**编译管道：**
```
模糊意图 → [解释器] → 结构化任务定义
                ↓
         [Harness 生成器] → 约束、工作流、技能
                ↓
         [Agent 工厂] → 专用代理拓扑（动态生成，非预设选择）
                ↓
         [编排器] → 执行计划
                ↓
         代理在生成的 harness 中执行 → 结果
                ↓
         失败反馈 → 元 Harness 改进
```

**快速开始：**
```bash
./scripts/bootstrap.sh "我需要一个客户入驻系统"
```

然后 AI 代理会读取 `META.md` 并运行整个管道。生成结果出现在 `generated/[project-name]/`。

---

## 项目结构

```
README.md           ← 你正在读的这个文件
META.md             ← 系统的 DNA（AI 代理的入口）
AGENTS.md           ← 项目规则（AI IDE 自动加载）
│
meta/               ← 编译管道的四个阶段
  interpreter.md      第 1 步：意图 → 结构化任务
  harness-generator.md 第 2 步：任务 → Harness
  agent-factory.md    第 3 步：Harness → 代理拓扑
  orchestrator.md     第 4 步：代理 → 执行计划
  examples/           参考示例（非预设模板）
    topologies.md       代理拓扑示例
│
templates/          ← 领域模板（生成的原材料）
  web-app/            Web 应用
  api-service/        API 服务
  data-pipeline/      数据管道
  content-system/     内容系统
  automation/         自动化
│
generated/          ← 生成输出（每次编译的结果）
memory/             ← 元知识（跨项目积累，越用越强）
  generation-log.md   每次生成都有记录
  meta-mistakes.md    生成失败 → 管道改进
  task-patterns.md    已知任务模式（加速解释）
  decisions.md        架构决策记录
  progress.md         执行进度
│
scripts/            ← 跨平台脚本（bash: Linux/macOS/WSL）
  bootstrap.sh        入口脚本
  verify-spec.md      声明式：检查什么
  verify.sh           可执行：怎么检查
  pre-task.sh         任务前检查
  quality-score.sh    健康指标
```

---

## 关键概念

### 什么是 Harness？

Harness 是围绕 AI 代理构建的**约束+工具+验证**系统。就像赛马需要缰绳（harness）才能跑对方向，AI 代理需要 harness 才能可靠地产出。

没有 harness 的代理：可能做对，可能做错，你不知道是哪种。
有 harness 的代理：做错了会被拦住，做对了会被验证，结果可预测。

### 为什么是"元"Harness？

普通 harness：人手动写规则 → 代理遵守规则
元 harness：人给意图 → **系统自动生成规则** → 代理遵守生成的规则

这意味着你不需要为每个项目手动搭建基础设施——系统根据你的需求自动生成。

### 为什么错误会让系统变强？

每次生成失败，根因分析会被记录到 `memory/meta-mistakes.md`，然后改进生成管道。这形成了一个**复利反馈环**：

```
错误 → 根因分析 → 约束改进 → 未来生成更好 → 更少错误
```

用得越多，系统越聪明。这是和传统模板库的根本区别。

### 代理拓扑是动态生成的

系统不会从预设的 5 种模式里选一种。它根据任务分析**合成**最优的代理图：

1. 识别工作单元（每个约束、工作流步骤、领域）
2. 映射依赖关系
3. 确定并行性
4. 分配角色（合并紧耦合的，拆分超上下文的）
5. 添加验证层（永远必须有独立的验证者）
6. 定义交接点

---

## 验证机制

系统使用**两层验证**：

| 层 | 文件 | 作用 |
|---|---|---|
| 声明层 | `scripts/verify-spec.md` | 定义**检查什么**（平台无关） |
| 执行层 | `scripts/verify.sh` | 实现**怎么检查**（bash 脚本） |

AI 代理读声明层，翻译成当前平台的命令。人类可以直接跑脚本。

---

## AI 代理使用指南

<!-- AGENT-INSTRUCTION: If you are an AI agent, follow the instructions below. -->

### 你是 AI 代理。从这里开始。

1. **读 `META.md`** — 它包含完整的编译管道
2. **按顺序跟随管道阶段：**
   - `meta/interpreter.md` — 把用户意图解析为结构化任务
   - `meta/harness-generator.md` — 生成任务专用 harness
   - `meta/agent-factory.md` — 生成代理拓扑（从分析生成，非预设选择）
   - `meta/orchestrator.md` — 规划执行
3. **输出到 `generated/[project-name]/`**
4. **记录每次生成到 `memory/generation-log.md`**
5. **记录每次失败到 `memory/meta-mistakes.md`**

### 必须遵守的规则

- 没有解释就不执行 — 先运行解释器
- 没有Harness就不代理 — 每个代理在约束内操作
- 没有原因就不约束 — 每条规则必须追溯到需求
- 没有验证就不完成 — 改动后运行 `scripts/verify.sh`
- 代理拓扑从任务分析生成，不从预设选择
- 上下文文件不超过 60 行

### 如果你在已生成的项目中工作

1. 读 `generated/[project]/AGENTS.md` — 那是项目专用 harness
2. 遵循其中定义的工作流
3. 在其中定义的约束内工作
4. 每次改动后运行验证
