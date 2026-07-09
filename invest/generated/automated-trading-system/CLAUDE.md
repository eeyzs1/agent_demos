# automated-trading-system — AGENT OPERATING INSTRUCTIONS

你是这个项目的执行 agent。本项目由 meta-harness 生成，harness 配置在当前目录。

## 启动前

1. 读 `task.yaml` —— 项目目标、domain、acceptance_criteria、hard_constraints
2. 读 `harness-scaffold.yaml` —— harness 结构 manifest（哪些 slot 已填充、哪些待填）
3. 读 `memory/session-state.yaml` —— 当前阶段、acceptance_criteria 进度

## 工作流

- 每个 work unit 从 `planning/work-units.yaml` 派发，由 `planning/dispatcher.py` 实例化 task card
- 每个 work unit 完成后跑 `python verification/self-check.py --verify-ac <task_id>` 校验
- 推进 phase 前跑 `python verification/hook-executor.py --event pre_advance_phase ...` 校验 gate
- 任何控制指令/状态变更必须经 `verification/audit-append.py` 写 audit_log（不可篡改）

## 硬约束（来自 task.yaml）

- 不得 mock/fake/stub 真实集成
- 不得绕过 audit_log
- 每条 acceptance_criteria 必须有可验证证据
- 配置支持热更新（不重启）

## 完成判定

`python orchestrator.py --verify` 返回 PASS = 所有 acceptance_criteria 已验证完成。
