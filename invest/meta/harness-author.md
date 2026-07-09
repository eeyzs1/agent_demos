# Meta-Harness Author: LLM 填充 Harness Slot 的指令

## 你的角色

scaffold.py 已经建好了 harness 骨架（目录 + 通用原语 + slot 种子基线）。
你的任务是：**分析 task.yaml，为每个 slot 改写出项目特定的内容**。

你不是在选模板，不是在套公式。你在**为这个具体项目合成它需要的约束/工具/验证**。

## 第一性原理

harness 回答一个问题："在这个具体项目上，agent 怎样才算可靠地干对了？"

答案的项目特定部分由你合成：
- 组件依赖图 → `constraints/architecture-rules.yaml` 的真实规则
- 数据流与敏感面 → `verification/security-guardrails.yaml` 的真实检查
- 工作单元与风险 → `planning/sub-agent-dispatch.yaml` 的真实拓扑
- 验收标准 → 每条都有对应验证器（traceability）

## 执行步骤

### Step 1: 读输入
1. 读 `task.yaml` —— 项目名、domain、real_need、goal、hard_constraints、acceptance_criteria、unknowns、assumptions、complexity
2. 读 `harness-scaffold.yaml` —— 列出所有待填充 slot + 每个 slot 的 guidance

### Step 2: 建立项目心智模型（先想清楚再写）
在脑中/草稿里回答：
- 这个项目有哪些组件/模块？（从 goal、hard_constraints、real_need 推断）
- 组件间依赖关系是什么？（谁调谁、数据怎么流）
- 哪些数据是敏感的？哪些操作是不可逆的？
- 验收标准如何可验证？每条对应什么检查？
- 这个 domain 有什么典型不变量？（如工业控制：安全联锁必须本地执行）

### Step 3: 逐个 slot 改写
对 `harness-scaffold.yaml` 的 `llm_slots` 列表里每个 slot：

1. 读 slot 文件的 seed 基线（scaffold 已复制，含通用结构）
2. 按 slot 的 `guidance` 字段 + 你的项目心智模型，改写文件内容
3. 保留文件的结构 schema（如 `rules: [{id, description, ...}]` 的字段名不变），替换内容
4. 内容必须引用 task 里真实的组件/模块/数据/约束——不能是通用占位

### Step 4: 自检（在交给 validate-harness.py 之前）
- 每个 acceptance_criteria 是否在某处有对应验证器？
- 是否引入了 mock/fake/stub/simulated 模式？（禁止）
- architecture-rules 的 dependency_direction 是否反映真实组件依赖？
- 是否所有引用的组件在 task.yaml 里存在？

## Slot 填充规范（按文件）

### context/knowledge-index.yaml
- `mappings`: 改为该项目的真实源码路径 → 知识域映射
- 每条带 `description` + `tags`（受控词汇）
- 例：工业控制项目可能有 `src/control/`、`src/edge/`、`src/cloud/`

### constraints/architecture-rules.yaml
- `rules`: 写该项目真实的架构约束（不是通用 web 规则）
  - 每条 `description` 必须引用 task 里真实的层/模块
  - `pattern`/`file_pattern` 针对该项目实际目录结构
- `dependency_direction`: allowed/forbidden 必须反映该项目的真实依赖图
  - 例：工业控制可能是 `edge → cloud`（允许）、`cloud → edge_control`（禁止——控制指令不能从云端下发到安全联锁）

### verification/security-guardrails.yaml
- `sensitive_data_filters`: 该项目实际敏感数据模式
  - 工业控制可能不是 email/credit_card，而是工艺参数、配方、安全阈值
- `dangerous_operations`: 该项目实际危险操作
  - 工业控制可能是 `控制指令从云端下发到安全联锁`、`绕过本地 interlock`

### planning/sub-agent-dispatch.yaml
- `prototypes`: 按 task 的工作单元合成 agent 角色
  - 不要套 `ceil(S/2)` 公式
  - 每个 role 的 responsibilities/receives/produces 针对该项目
  - 例：工业控制可能有 `control-engineer`、`safety-reviewer`、`protocol-validator` 而不是通用 planner
- **每个 prototype 必须含完整字段**：
  - `responsibilities`（语义角色描述）
  - `receives`（输入工件清单——subagent 可读的文件/资源）
  - `produces`（输出工件清单——subagent 写出的产物，下游 receives 必须能对上）
  - `count`（整数或公式如 `ceil(S/2)`，由 agent-factory.py 评估）
  - `condition`（可选，因子谓词如 `C>=4`，决定 prototype 是否启用）
  - `boundaries.cannot`（不得越界的操作清单）
  - `boundaries.max_context_lines`（上下文预算——dispatcher 会把它写入 task card）
  - `requires_human_review`（可选，true 时 dispatcher 在该 work unit 后暂停，runtime 必须等人工）

### planning/work-units.yaml（**新增**）
- `work_units`: 把 task 分解为可独立派发的工作单元
- **不要在这里硬塞顺序**——只声明 `depends_on`，让 dispatcher + dag-builder.py
  做拓扑排序与并行分组（脚本负责算法，你负责语义切分）
- 每条字段：
  - `id`：唯一标识（如 `WU001`）
  - `name`：人类可读的目标（如 "实现 edge PID 闭环控制"）
  - `assigned_to`：必须引用 sub-agent-dispatch.yaml 里某个 prototype 名（dispatcher 校验一致性）
  - `workflow`（**重要**）：本 work_unit 所属的 workflow 名（必须与 flow-control.yaml
    的 `workflows` key 一致）。agent-factory.py 用此字段派生每个 role 的 assigned_workflows
    —— **不要靠关键词匹配推断 workflow→role**，要在这里显式声明。
  - `depends_on`：依赖的其他 work_unit id 列表（**必须基于真实依赖**——如下游用上游的产物；不是凭感觉排序）
  - `success_criteria`：本 work_unit 完成的可验证证据（每条应 trace 到 task.acceptance_criteria）
  - `traces_to`（**重要**）：本 work_unit 验收的 AC id 列表（如 `[AC1, AC4]`）。
    agent-factory.py 用此字段派生每个 role 的 assigned_criteria——**不要靠关键词匹配推断 AC→role**，
    要在这里显式声明。
  - `constraints`（可选）：本 work_unit 必须遵守的 architecture-rules id 列表（dispatcher 写入 task card）
  - `requires_human_review`（可选）：本 work_unit 完成后必须人工 review（与 prototype 同字段并集）
- **分解决策**：acceptance_criteria 不是 work_unit（一个 AC 可能要多个 WU，多个 WU 也可能共享一个 AC）；
  按"可独立派发 + 可独立验证"的粒度切分

### planning/budget.yaml
- 按该项目实际复杂度设置 step/token/retry 预算
- 不是 web-app 默认值
- 可选 `per_role_budget`：按 agent prototype 设置不同预算（如 safety-engineer 预算更紧）

### memory/session-state.yaml（**schema 强制**）
- **必须用以下 schema**（guard.py / orchestrator.py 强制读这个结构）：
  ```yaml
  status: initialized          # initialized | in_progress | completed | blocked
  phase: GENERATE              # 当前 pipeline phase
  progress:
    acceptance_criteria:       # 必须在 progress 下，不是顶层
      - id: AC1
        description: "..."
        status: pending       # pending | in_progress | completed | failed
        verifier: "tests/..."
        traces_to: "..."
    completed_criteria: []    # 已完成的 AC id 列表
    failed_criteria: []        # 失败的 AC id 列表
  guard_log: []
  blockers: []
  ```
- **不要**把 `acceptance_criteria` 放在顶层（guard.py 读 `state.progress.acceptance_criteria`，找不到会 FAIL 报"No acceptance criteria loaded"）
- 每条 AC 的 `id` / `description` / `verifier` / `traces_to` 从 task.yaml 派生
- guard.py 在 hook-executor HOOK_PHASE_GATE 跑时读本文件，schema 不一致会让 hook 永远 FAIL

### evolution/genome.yaml
- `constraints`: 把 task 的 hard_constraints 作为种子约束写入（每条带 id/rule/source）
- `workflows`: 从 task 派生

### evolution/domain-advancements.yaml
- 按该项目领域写四阶段进阶（Basic/Solid/Advanced/Excellent）
- 例：工业控制的 Advanced 可能是"预测性维护"、"数字孪生"，不是 web-app 的"离线支持"

### 项目特定脚本生成（非 slot，但必须做）

flow-control.yaml 与 runtime-hooks.yaml 的 `command` 字段会引用 `python verification/xxx.py`。
其中通用原语（audit-append / lint-check / dispatch-verifier / hook-executor / self-check /
consistency-check / anti-mock-check / quality-gate 等）由 scaffold.py 自动复制；
但**项目特定的验证脚本**（如 scan-plaintext / scan-log-masking）必须由你基于
architecture-rules / security-guardrails 生成。

执行步骤：
1. 扫描 `planning/flow-control.yaml` 的 `workflows.*.steps[].command` 与 `mandatory_pre_steps[].command`
2. 扫描 `verification/runtime-hooks.yaml` 的 `events.*.checks[].command`
3. 提取所有 `python verification/<name>.py` 里的 `<name>.py`
4. 对每个不在通用原语列表里的脚本（即你首次见到的名字），生成实现：
   - 读 `constraints/architecture-rules.yaml` / `verification/security-guardrails.yaml`，
     理解它要检查的规则（如 AR005 明文配方）
   - 实现 CLI：`argparse` + `--project-root`（+ 需要的标志如 `--recipe` / `--pii`）
   - exit 0 = PASS，exit 1 = FAIL（发现违规）
   - 写到 `verification/<name>.py`

validate-harness.py 的 check #7 会校验所有引用的脚本存在——缺失报 WARNING。
不生成 = harness 不自洽（runtime 调用时会 FileNotFoundError）。

## 硬约束（不可违反）

1. **NO mock/fake/stub/simulated** —— 不能在 slot 内容里写 mock 实现
2. **NO 通用占位** —— 内容必须引用 task 真实实体；不能留 "TODO" 或 "example"
3. **保留 schema 结构** —— 文件的字段名/层级不变，只换内容
4. **acceptance_criteria traceability** —— 每条验收标准必须在某 slot 里有对应验证手段
5. **不删通用原语** —— scaffold 复制的 anti-mock/self-check/evolution 等不动
6. **domain 由 task 决定** —— 不从 5 个固定桶选；按 task 实际领域合成

## 完成后

```
python scripts/validate-harness.py <output_dir>
```

校验通过 = harness 可用。校验失败 = 按 report 修正对应 slot。
