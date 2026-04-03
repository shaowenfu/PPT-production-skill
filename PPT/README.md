# PPT Workspace Log

`PPT/` 是本仓库所有 PPT 项目的 `workspace（工作区）` 和 `artifact store（中间产物存储区）`。

规则：
- 每个项目只使用自己的目录：`PPT/<project_id>/`
- 默认只处理**当前用户明确指定**的 `project_id`
- 除非用户显式要求继续、检查或修复历史项目，否则不要读取或修改其他项目目录
- 如果一个用户请求被拆成多个子 PPT 项目，先在 `Project Queue` 中登记，再按顺序逐个执行
- 同一时刻只能有一个 `IN_PROGRESS`
- 默认只处理 `IN_PROGRESS` 项目；除非用户显式要求切换顺序或继续其他历史项目
- 开始一个新项目时，必须在本文件追加一条 `start` 记录
- 完成一个项目时，必须在本文件追加一条 `finish` 记录

记录格式：

```md
- YYYY-MM-DD HH:MM | <project_id> | start  | 简短动作说明
- YYYY-MM-DD HH:MM | <project_id> | finish | 简短结果说明
```

示例：

```md
- 2026-04-03 16:52 | ai_telecom_trends | start  | 新项目进入工作流
- 2026-04-03 17:30 | ai_telecom_trends | finish | 生成 deck/deck.pptx
```

## Project Queue

仅在一个大请求被拆成多个子 PPT 项目时使用。

规则：
- `status` 只使用 `PLANNED / IN_PROGRESS / DONE`
- 同一个拆分任务中，只能有一个 `IN_PROGRESS`
- 当前 `IN_PROGRESS` 完成后，再把下一个 `PLANNED` 改成 `IN_PROGRESS`

格式：

```md
| parent_request | project_id | status | note |
| --- | --- | --- | --- |
| telecom_2026_master | telecom_2026_part1 | IN_PROGRESS | 第一模块：行业背景与趋势 |
| telecom_2026_master | telecom_2026_part2 | PLANNED | 第二模块：能力建设与案例 |
```

当前无拆分中的多项目任务。

## Existing Projects

- ai_telecom_trends | 历史项目，目录存在
- ai_telecom_trends_old | 历史项目，目录存在
- test_asset_smoke | 测试项目，目录存在
- test_review_flow | 测试项目，目录存在
- test_review_flow_2 | 测试项目，目录存在

## Project Log

- 2026-04-03 16:52 | workspace | init   | 建立 `PPT/README.md`，作为项目历史登记簿
- 2026-04-03 17:00 | workspace | update | 增加多子项目 `IN_PROGRESS` 队列规则
