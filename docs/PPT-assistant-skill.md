# PPT-assistant-skill

## Purpose

为 `openClaw` 提供一份可执行的 `assistant-skill`，用于在 `PPT workflow`（PPT 工作流）中：

- 定位本项目仓库路径与 `PPT/` 目录
- 确认当前正在处理的具体项目
- 进入对应 `project workspace`（项目工作区）
- 读取 `Workflow state store`（工作流状态存储）
- 根据当前状态选择下一步动作
- 将中间结果发给用户审阅
- 根据反馈执行局部回退与重跑

## Trigger

当出现以下任一情况时，应触发 `PPT-assistant-skill`：

- 用户明确说“调用 `PPT-assistant-skill`”
- 用户提出 `PPT制作`、课程 `PPT` 生成、讲义转 `PPT`、大纲转 `PPT`、批量生成 `PPT` 等请求

触发后，`openClaw` 不应直接开始生成内容，而应先执行本 `Skill` 的入口协议。

## When To Use

- 用户要从 `Word/PDF/text` 大纲生成完整 `PPT`
- 用户要继续某个已有 `PPT` 项目
- 用户要对某个 `PPT` 项目的文案、页面类型策略、图片或排版做迭代

## When Not To Use

- 用户只是在讨论 `PPT` 想法，还没有进入项目执行
- 用户只是要单张图片，不需要 `PPT workflow`
- 用户只是要改某个现成 `pptx` 文件中的一个字，且不需要整个状态流转

## Scope

本 `assistant-skill` 负责：

- 项目识别与上下文切换
- 仓库路径与 `PPT/` 目录定位
- 状态读取与状态流转
- 中间结果审阅与用户反馈接收
- 决定调用哪个 `Python tool`
- 决定局部重跑边界

本 `assistant-skill` 不负责：

- 直接解析 `Word/PDF/text`
- 直接生成逐页文案
- 直接生成图片
- 直接拼装 `PPTX`

这些动作由独立 `Python tools` 完成。

## Entry Protocol

每次进入本工作流时，`openClaw` 必须严格按以下顺序执行：

1. 找到本项目仓库路径
2. 找到仓库下的 `PPT/` 目录
3. 进入 `PPT/` 目录
4. 向用户确认当前进行的项目序号或 `project_id`
5. 进入对应的 `project workspace`
6. 读取当前项目的 `Workflow state store`
7. 检查当前状态对应的已有产物是否存在
8. 根据当前状态决定下一步动作，而不是凭会话上下文猜测

如果用户没有提供项目序号或 `project_id`，不得直接推进后续步骤。

## Inputs

本 `Skill` 的输入分为 4 类：

1. 用户输入

- `project_id` 或项目序号
- 当前需求描述
- 用户反馈
- 用户上传的大纲源文件或其路径

2. 仓库上下文

- 本项目仓库根路径
- `PPT/` 目录路径
- 对应项目工作目录路径

3. 状态输入

- `state.json`
- 当前状态对应的产物文件
- 历史反馈记录

4. 工具输入

- 各 `Python tools` 所需参数
- 上一状态产物的路径

## Outputs

本 `Skill` 的输出分为 4 类：

1. 用户可见输出

- 当前项目识别结果
- 当前状态说明
- 中间产物预览或摘要
- 需要用户确认的审阅请求
- 最终交付说明

2. 状态输出

- 更新后的 `state.json`
- 新的 `current_state`
- `last_completed_step`
- `feedback_history`
- `retry_count`

3. 产物输出

- `outline.json`
- `slide_draft.json`
- `plan.json`
- `prompts.json`
- 覆盖全部页面的图片资产
- `deck.pptx`
- 最终导出文件

4. 路由输出

- 下一步应调用的 `Python tool`
- 是否需要用户确认
- 是否需要局部回退

## Project Workspace

建议目录结构：

```text
PPT/{project_id}/
├── state.json
├── outline/
│   └── outline.json
├── draft/
│   └── slide_draft.json
├── plan/
│   └── plan.json
├── prompts/
│   └── prompts.json
├── assets/
├── deck/
│   └── deck.pptx
└── exports/
```

## Workflow State Store

建议 `state.json` 至少包含：

```json
{
  "project_id": "ppt-demo-001",
  "current_state": "DraftGenerated",
  "last_completed_step": "slide_draft_generate",
  "artifacts": {},
  "feedback_history": [],
  "retry_count": {},
  "updated_at": "2026-03-24T00:00:00+08:00"
}
```

## State Machine

### 1. OutlineImported

含义：
课程大纲已经导入并完成标准化。

必备产物：

- `outline/outline.json`

允许动作：

- 运行 `slide_draft_generate.py`
- 请求用户重新上传或替换大纲

默认下一步：

- 进入 `DraftGenerated`

用户反馈处理：

- 如果用户要求更换源文件，回到本状态并重新执行 `outline_ingest.py`

### 2. DraftGenerated

含义：
已根据大纲生成《PPT逐页文案稿》。

必备产物：

- `draft/slide_draft.json`

允许动作：

- 向用户发送逐页文案稿进行审阅
- 根据反馈局部重跑文案生成
- 在用户确认后进入页面规划

默认下一步：

- 用户确认文案后进入 `PlanConfirmed`

用户反馈处理：

- 用户修改标题、正文、金句：留在本状态，重跑 `slide_draft_generate.py` 或局部编辑 `slide_draft.json`
- 用户补充大纲约束：必要时回退到 `OutlineImported`

### 3. PlanConfirmed

含义：
已完成页面类型判定和视觉策略规划。

必备产物：

- `plan/plan.json`

`plan.json` 至少应包含：

- 页面顺序
- A/B 类分类
- 每页的 `prompt_strategy`
- 目标 A/B 比例与实际 A/B 比例
- 每页的风格标签

允许动作：

- 向用户发送《页面视觉规划清单》
- 根据反馈调整 A/B 分类、比例目标或风格标签
- 在用户确认后进入资产生成

默认下一步：

- 用户确认后进入 `AssetsGenerated`

用户反馈处理：

- 用户质疑某页分类：留在本状态，重跑 `slide_plan_generate.py`
- 用户修改风格方向：留在本状态，更新 `plan.json`
- 用户要求调整 A/B 比例：留在本状态，重跑 `slide_plan_generate.py`
- 用户修改文案本身：回退到 `DraftGenerated`

### 4. AssetsGenerated

含义：
已完成全部页面的 `Prompt` 生成和图片生成，其中 A/B 仅决定提示词策略，不决定是否出图。

必备产物：

- `prompts/prompts.json`
- `assets/` 下对应图片文件

允许动作：

- 向用户展示页面图片预览
- 根据反馈局部重跑视觉生成
- 在用户确认后进入整包拼装

默认下一步：

- 用户确认后进入 `DeckAssembled`

用户反馈处理：

- 用户要求换风格、换意象、换构图：留在本状态，重跑 `visual_prompt_generate.py` 和/或 `visual_asset_generate.py`
- 用户要求把某页从 A 类改成 B 类，或反之：回退到 `PlanConfirmed`
- 用户要求修改文案：回退到 `DraftGenerated`

### 5. DeckAssembled

含义：
已完成 `PPTX` 首版拼装。

必备产物：

- `deck/deck.pptx`

允许动作：

- 向用户发送首版 PPT
- 根据反馈局部修改排版、图片或文案
- 在用户确认后进入最终审批

默认下一步：

- 用户确认后进入 `FinalApproved`

用户反馈处理：

- 用户只改排版：留在本状态，重跑 `ppt_assemble.py`
- 用户改图片：回退到 `AssetsGenerated`
- 用户改分类：回退到 `PlanConfirmed`
- 用户改文案：回退到 `DraftGenerated`

### 6. FinalApproved

含义：
最终版本已确认，可导出和归档。

必备产物：

- `exports/` 下最终交付文件

允许动作：

- 导出最终版
- 写入归档记录
- 结束流程

用户反馈处理：

- 如果用户在最终确认后仍提出修改，按修改范围回退到对应状态，不直接覆盖最终归档

## Transition Rules

主路径：

```text
OutlineImported
  -> DraftGenerated
  -> PlanConfirmed
  -> AssetsGenerated
  -> DeckAssembled
  -> FinalApproved
```

局部回退规则：

- 文案问题 -> 回退到 `DraftGenerated`
- 分类、比例或风格规划问题 -> 回退到 `PlanConfirmed`
- 图片问题 -> 回退到 `AssetsGenerated`
- 纯排版问题 -> 回退到 `DeckAssembled`
- 源文件问题 -> 回退到 `OutlineImported`

## Python Tools

建议将以下步骤固定为 `Python tools`：

1. `project_init.py`
初始化项目目录和 `state.json`

2. `outline_ingest.py`
解析 `Word/PDF/text`，输出统一 `outline.json`

3. `slide_draft_generate.py`
生成 `slide_draft.json`

4. `slide_plan_generate.py`
生成 `plan.json`

5. `visual_prompt_generate.py`
生成 `prompts.json`

6. `visual_asset_generate.py`
生成覆盖全部页面的图片资产

7. `ppt_assemble.py`
拼装 `deck.pptx`

## Design Update Note

当前正式口径如下：

- A/B 不是执行分支，而是 `prompt strategy`（提示词策略）分支
- 所有页面都必须生成图片资产
- `ppt_assemble.py` 默认假定每一页都有对应图片资产
- 页面类型判定必须内置 A/B 比例约束，禁止出现全 A 或全 B 的退化结果

## openClaw Responsibilities

`openClaw` 在本工作流中的职责：

- 确认仓库路径与 `PPT/` 目录
- 确认 `project_id`
- 读取 `state.json`
- 检查当前状态的必备产物
- 决定调用哪个 `Python tool`
- 向用户展示中间或最终结果
- 接收反馈并识别反馈作用域
- 决定回退到哪个状态
- 写回新的状态与反馈记录

## Failure Handling

必须显式失败，禁止静默吞错。失败时应区分以下几类：

1. `ProjectResolutionError`

- 找不到仓库路径
- 找不到 `PPT/` 目录
- 找不到对应 `project_id` 目录

处理方式：

- 停止后续流程
- 向用户报告缺失的路径信息
- 要求用户确认项目序号、目录或初始化新项目

2. `StateStoreError`

- `state.json` 缺失
- `state.json` 结构不合法
- 当前状态与产物不一致

处理方式：

- 停止自动流转
- 报告状态损坏或缺失
- 要求执行状态修复或重新初始化

3. `InputError`

- 用户未提供大纲文件
- 输入文件格式不支持
- 必需参数缺失

处理方式：

- 不进入生成步骤
- 明确指出缺少什么输入

4. `ToolExecutionError`

- `Python tool` 执行失败
- 依赖缺失
- 外部模型调用失败

处理方式：

- 记录失败步骤和错误上下文
- 不推进状态
- 允许在修复环境后重试当前步骤

5. `FeedbackConflictError`

- 用户反馈跨多个层级且互相冲突
- 当前反馈无法映射到单一回退边界

处理方式：

- 由 `openClaw` 请求用户澄清
- 在澄清前不执行重跑

## Success Criteria

本 `Skill` 成功的标准不是“跑完一次”，而是满足以下条件：

1. `openClaw` 能稳定找到仓库路径、`PPT/` 目录和项目目录
2. `openClaw` 每次都先读 `state.json` 再决策，而不是凭上下文猜
3. 六个状态之间的主路径和回退路径明确、可执行
4. 每个状态都有对应必备产物，且产物缺失时能显式报错
5. 用户反馈能被映射到明确的回退层级
6. 文案、分类、图片、排版修改可以局部重跑，而不是整链路重跑
7. 最终能稳定导出可交付的 `PPTX`

## Feedback Scope Rules

必须显式限制反馈作用域，避免整条链路无脑重跑：

- 文案反馈只影响 `copy layer`
- 分类反馈只影响 `planning layer`
- 视觉反馈只影响 `asset layer`
- 排版反馈只影响 `assembly layer`

只有当上游输入本身发生变化时，才允许跨层回退。

## Example

用户说：

```text
调用 PPT-assistant-skill，继续项目 03 的 PPT 制作。
```

`openClaw` 应执行：

1. 定位本项目仓库路径
2. 定位并进入 `PPT/` 目录
3. 确认项目 `03`
4. 进入 `PPT/03/`
5. 读取 `state.json`
6. 根据 `current_state` 选择下一步动作
7. 如果当前状态是 `AssetsGenerated`，则向用户展示预览并请求确认，而不是回到大纲阶段重跑
