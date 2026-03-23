# Contributing

## 目的

本文件定义向仓库新增 `Skill` 或 `Python script` 时，必须补齐的最小信息与约束。

目标不是增加流程负担，而是保证新增能力满足三个条件：

- 可理解
- 可复用
- 可验证

`Tasks/` 可以作为需求来源、设计工作区与灵感来源，但不能替代这里要求的正式说明。它是开发期脚手架，不是正式能力体系的一部分。

## 提交前总原则

新增任何能力前，先判断它属于哪一类：

- `Tasks/ working area`（开发工作区）：用于编写需求、设计、草稿和中间产物，服务于能力孵化，后续可移除
- `Skill`：需要沉淀成稳定流程与约束
- `Python script`：需要沉淀成稳定执行能力
- `Skill + script`：既要定义流程，也要提供可执行机械臂

如果一个内容还只是开发材料，就先放在 `Tasks/`。如果它已经具备复用价值、输入输出和边界可以说清楚，再升格为 `Skill` 或脚本。

## 新增 Skill 必须补的内容

每个 `Skill` 至少必须补齐以下内容：

### 1. 基本信息

- `name`：Skill 名称
- `purpose`：这个 Skill 解决什么问题
- `when to use`：什么情况下应该使用它
- `when not to use`：什么情况下不应该使用它

### 2. 输入与输出

- `inputs`：需要什么输入信息
- `outputs`：预期产出是什么
- `dependencies`：是否依赖特定脚本、模板、目录或外部环境

### 3. 工作流程

- `workflow`：执行步骤
- `decision points`：关键分支判断点
- `failure handling`：失败时应该如何处理或升级

### 4. 边界与契约

- `non-goals`：明确不解决什么问题
- `assumptions`：这个 Skill 成立依赖哪些前提
- `handoff`：如果需要调用脚本，调用关系必须写清楚

### 5. 验证方式

- `success criteria`：怎么判断这个 Skill 输出合格
- `example`：至少给一个最小示例，帮助理解使用方式

## 推荐的 Skill 文档模板

建议每个 `Skill` 文档至少包含这些段落：

```md
# <Skill Name>

## Purpose

## When To Use

## When Not To Use

## Inputs

## Outputs

## Workflow

## Failure Handling

## Non-goals

## Example
```

## 新增 Python script 必须补的内容

每个脚本至少必须补齐以下内容：

### 1. 基本信息

- `name`：脚本名称
- `purpose`：脚本负责执行什么动作
- `owner scope`：脚本职责边界，只做什么，不做什么

### 2. 输入输出契约

- `inputs`：输入参数、输入文件、环境变量
- `outputs`：标准输出、输出文件、返回结果
- `exit codes`：退出码语义

### 3. 依赖说明

- `runtime`：Python 运行环境要求
- `dependencies`：依赖哪些 package（包）、系统命令、外部资源
- `setup`：如何准备运行环境

### 4. 错误语义

- 哪些错误属于输入问题
- 哪些错误属于环境问题
- 哪些错误属于目标对象本身的问题
- 失败时输出什么信息，是否返回非零退出码

禁止静默吞错。

### 5. 使用说明

- `usage`：命令行调用示例
- `example input/output`：最小输入输出示例
- `limitations`：已知限制

### 6. 验证方式

- 至少提供一种验证方式：测试、断言、dry-run（演练模式）或最小手工验证步骤

## 推荐的脚本说明模板

如果脚本复杂度足够高，建议在脚本同目录放一个说明文档，至少包含：

```md
# <Script Name>

## Purpose

## Inputs

## Outputs

## Dependencies

## Usage

## Exit Codes

## Error Semantics

## Limitations

## Verification
```

## Skill 与 script 的映射要求

如果一个 `Skill` 依赖某个脚本，那么至少要满足：

- `Skill` 文档中写清楚调用哪个脚本
- 脚本说明中写清楚它服务哪类任务
- 两边的输入输出语义不能互相矛盾

如果二者不能稳定对应，说明能力边界还没想清楚，不应合并进主干能力体系。

## 与 Tasks 的关系

`Tasks/` 中的文件可以提供：

- 原始需求
- 设计文档
- 草稿
- 素材
- 头脑风暴上下文

但当你决定新增 `Skill` 或脚本时，必须把稳定信息从 `Tasks/` 中提炼出来，补齐到正式文档里。不要让长期能力依赖某个开发期任务文件才能被理解。能力稳定后，`Tasks/` 中对应材料应视为可清理、可移除的脚手架，而不是正式交付物。

## 最小检查清单

提交前至少自检以下问题：

1. 这是复用能力，而不是一次性任务残留吗？
2. 输入输出是否明确？
3. 非目标是否明确？
4. 错误能否被调用方识别和处理？
5. 是否给出了最小示例或验证方式？
6. 如果它起源于 `Tasks/`，关键上下文是否已经提炼出来，使能力在脱离 `Tasks/` 后仍可独立理解？

如果以上问题答不上来，就先不要提交为正式能力。
