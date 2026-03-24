# PPT `state.json` Schema

## 顶层结构
```json
{
  "schema_version": "1.0",
  "project_id": "项目ID",
  "current_state": "当前状态",
  "last_completed_step": "最近成功步骤",
  "artifacts": {
    "outline": { "path": "outline/outline.md", "exists": true },
    "draft": { "path": "draft/slide_draft.json", "exists": true },
    "plan": { "path": "plan/plan.json", "exists": true },
    "prompts": { "path": "prompts/prompts.json", "exists": true },
    "assets_manifest": { "path": "assets/manifest.json", "exists": true },
    "deck": { "path": "deck/deck.pptx", "exists": true }
  },
  "feedback_history": [],
  "transition_history": []
}
```

## 核心状态说明
- `Initialized`: 项目骨架已建立。
- `OutlineImported`: 大纲 `outline.md` 已就绪。
- `DraftGenerated`: 深度文案 `slide_draft.json` 已生成。
- `PlanConfirmed`: 25 页逻辑规划 `plan.json` 已完成。
- `AssetsGenerated`: 阿里云生成的图片集已落盘。
- `DeckAssembled`: 最终 `.pptx` 封装完成。
