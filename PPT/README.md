# PPT Workspace Log

`PPT/` 是本仓库所有 PPT 项目的 `workspace（工作区）` 和 `artifact store（中间产物存储区）`。

规则：
- 每个项目只使用自己的目录：`PPT/<project_id>/`
- 默认只处理**当前用户明确指定**的 `project_id`
- 除非用户显式要求继续、检查或修复历史项目，否则不要读取或修改其他项目目录
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

## Existing Projects

- ai_telecom_trends | 历史项目，目录存在
- ai_telecom_trends_old | 历史项目，目录存在
- test_asset_smoke | 测试项目，目录存在
- test_review_flow | 测试项目，目录存在
- test_review_flow_2 | 测试项目，目录存在

## Project Log

- 2026-04-03 16:52 | workspace | init   | 建立 `PPT/README.md`，作为项目历史登记簿
- 2026-04-05 00:00 | workspace | update | 移除 `Project Queue`，保留轻量项目登记规则
