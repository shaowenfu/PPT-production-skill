---
name: ppt-production-expert
description: Drive the seven-step AI PPT workflow for this GitHub repository after an agent clones it locally. Use this skill whenever the user wants to create, continue, repair, or fully deliver a PPT project under `PPT/`, including writing `outline/outline.md`, authoring or fixing `plan/plan.json`, generating slide drafts, designing visual prompts, rendering assets, or assembling `deck/deck.pptx`. Also use it whenever the user asks to resume from `state.json`, recover a broken PPT step, or directly produce a final PPT from this repo even if they do not mention the skill by name.
compatibility:
  - git
  - bash
  - python
---

# PPT Production Expert

Use this skill after the agent clones this repository. Treat this document as the primary `SOP（标准作业程序）`. Do not inspect source code unless a command fails, required config is missing, or an artifact is structurally invalid.

## Core model

This repo produces PPT in a specific way:

- `final slide` = one `full-bleed image（全屏视觉图）`
- `detailed talking content` = `speaker notes（演讲者备注）`
- `slide_draft.json` is the content knowledge base for later visual and note generation
- `no text pollution` means no messy AI-rendered junk text on the image; it does not mean the deck has no information

Do not redesign this rendering model during execution. Follow it.

## Operating assumptions

1. Treat the directory containing `SKILL.md` as `repo root`.
2. Resolve all paths relative to `repo root`. Never assume any absolute filesystem path.
3. If the repo is not present locally yet, clone it first from `https://github.com/shaowenfu/PPT-production-skill.git` and then work from that cloned `repo root`.
4. Before any Python step:
   - if `venv/` does not exist, run `python -m venv venv`
   - run `source venv/bin/activate`
   - run `pip install -r requirements.txt`
5. Keep `aspect ratio` fixed at `16:9`.
6. For Google image generation, request `image_size="2K"` and keep `aspect ratio` at `16:9`.
7. Prefer `./skill.sh` for all script-backed steps. It is the stable thin entry.
8. Keep atomic script boundaries intact. Do not merge the workflow into one custom script.
9. When resuming a project, read `PPT/<project_id>/state.json` first.
10. Required credentials:
   - `GOOGLE_API_KEY` for default text generation and image generation, ask user to set it up in .env or ask them to provide it and write into .env directly if missing(**required**)
   - `DEEPSEEK_API_KEY` for text generation fallback(**optional**)
   - `OFOX_API_KEY` for image generation fallback(**optional**)
11. Default providers are hardcoded in `pptflow/config.py`:
   - text: `google`
   - image: `google`
   - switch to fallback providers by editing those constants directly

## Default execution policy

- Do not run the full seven-step workflow continuously by default.
- After each step that creates or changes an artifact, stop and ask the user to review that artifact before proceeding.
- Use the artifact itself as the review surface. Do not dump the entire prompt into chat unless the user asks for it.
- The primary review files are:
  - step 2: `outline/outline.md`
  - step 3: `plan/plan.json`
  - step 4: `draft/slide_draft.json`
  - step 5: `prompts/screen_text.json`
  - step 6: generated images under `assets/`
- `prompts/prompts.json` is the machine-facing file for image generation. Show it only when the user wants full prompt detail or when you need to manually sync it with approved on-slide text.
- If the user edits `prompts/screen_text.json`, update `prompts/prompts.json` so the quoted Chinese text matches the approved screen text before running step 6.
- Only stop automatically on real blockers:
  - missing source material
  - missing credentials
  - command failure
  - invalid or missing required artifact
- If a step is manual, complete it directly instead of waiting for a later script to fail.
- If a question is non-blocking, follow this `SKILL.md` and continue. Do not inspect code just to “double check”.

## Script responsibility table

| Step | Backing mode | What it does | Scope |
| --- | --- | --- | --- |
| `init` | script | creates workspace and state files | one project |
| `draft` | script | generates deep page content into `draft/slide_draft.json` | only requested `page_ids` |
| `prompt` | script | generates user-reviewable screen text plus visual prompts from draft content | supports full run, selected pages, and parallel batches |
| `assets` | script | generates slide images from prompts | supports full run, selected pages, and parallel generation |
| `assemble` | script | packs images into `deck.pptx` and writes notes | one final deck |

Manual steps:

- `outline` is direct agent writing
- `plan` is direct agent writing

## Seven-step workflow

### Step 1: Project Init

Goal:
Create a new PPT workspace.

Action:
```bash
./skill.sh --step init --project-dir PPT/<project_id>
```

Output:
- `PPT/<project_id>/state.json`
- standard project directories

Done when:
- the project directory exists
- `state.json` exists

### Step 2: Outline Ingest

Goal:
Turn the user raw material or source outline into a production-ready chapter structure and ask for user confirmation.

Action:
Write `PPT/<project_id>/outline/outline.md` directly. Do not use a script.

Output:
- `PPT/<project_id>/outline/outline.md`

Done when:
- the outline is in Simplified Chinese
- the structure is coherent and presentation-ready
- the chapter flow matches the user goal

Minimal example:
```md
# 趋势洞察：AI时代通信运营新机遇

## 1. 时代背景与行业变化
- AI 从工具升级为产业基础设施
- 通信运营商从管道角色走向能力平台角色

## 2. 通信运营商的新机会
- 网络、数据、算力、渠道和行业客户资源的再组合
- 从连接服务延展到智能服务

## 3. 落地路径与行动建议
- 试点场景选择
- 能力建设重点
- 组织与协同机制
```

### Step 3: Slide Planning

Goal:
Convert the outline into a slide-by-slide execution plan.

Action:
Write `PPT/<project_id>/plan/plan.json` directly. Do not use a script.

Output:
- `PPT/<project_id>/plan/plan.json`

Done when:
- page count is `25` by default unless the user says otherwise
- `page_id` is unique and sequential like `p1`, `p2`, `p3`
- `category` uses only `A` or `B`
- `B` pages stay within `20%-40%`
- every page has a deliberate `layout_type`

Planning rules:
- decide `layout_type` in `plan.json`, not later in prompt generation
- `layout_type` should express information structure, not visual style keywords
- avoid using a single `A`-page type for everything
- recommended `layout_type` vocabulary:
  - `cover`
  - `section_header`
  - `bullet_points`
  - `comparison`
  - `process_flow`
  - `framework`
  - `case_study`
  - `data_evidence`
  - `image_only`
  - `summary`
- adjacent pages should not all share the same `layout_type`

Minimal example:
```json
{
  "pages": [
    {
      "page_id": "p1",
      "title": "趋势洞察：AI时代通信运营新机遇",
      "category": "B",
      "content_hint": "封面与主题建立",
      "layout_type": "cover"
    },
    {
      "page_id": "p2",
      "title": "为什么现在必须重新看待运营商价值",
      "category": "A",
      "content_hint": "提出核心判断与价值重估逻辑",
      "layout_type": "comparison"
    }
  ]
}
```

### Step 4: Deep Content Generation

Goal:
Generate substantial business content for selected slides.

Action:
Run by batches over requested `page_ids`:
```bash
./skill.sh --step draft --project-dir PPT/<project_id> --page-ids p1,p2,p3,p4,p5
```

Output:
- `PPT/<project_id>/draft/slide_draft.json`

Done when:
- requested pages exist in `slide_draft.json`
- content is substantive, not just title restatement
- stop and ask the user to review `slide_draft.json` before step 5

### Step 5: Visual Prompt Design

Goal:
Convert slide draft content into user-confirmable on-slide text and image-generation prompts.

Action:
Run one page:
```bash
./skill.sh --step prompt --project-dir PPT/<project_id> --target-pages p8 --parallel 1
```

Run full or batch generation:
```bash
./skill.sh --step prompt --project-dir PPT/<project_id> --batch-size 5 --parallel 3
```

Output:
- `PPT/<project_id>/prompts/screen_text.json`
- `PPT/<project_id>/prompts/prompts.json`

Done when:
- `screen_text.json` exists
- `prompts.json` exists
- requested pages are present in `screen_text.json`
- requested pages are present in `prompts.json`
- prompts avoid watermark language and stray rendered text
- stop and ask the user to review `screen_text.json` before step 6

Review rule:
- `screen_text.json` is the primary review file because it only contains `page_id` and final on-slide text.
- If the user changes `screen_text.json`, sync the corresponding quoted Chinese text in `prompts.json` before generating assets.

### Step 6: Visual Asset Generate

Goal:
Render slide images from prompts.

Action:
Run full generation:
```bash
./skill.sh --step assets --project-dir PPT/<project_id> --parallel 3
```

Run one page or rerun selected pages:
```bash
./skill.sh --step assets --project-dir PPT/<project_id> --target-pages p8 --parallel 1
./skill.sh --step assets --project-dir PPT/<project_id> --target-pages p8,p9 --parallel 2 --overwrite
```

Output:
- `PPT/<project_id>/assets/manifest.json`
- image files under `PPT/<project_id>/assets/`

Done when:
- requested images exist
- image aspect ratio is `16:9`
- stop and ask the user to review the images before step 7

### Step 7: PPT Assemble

Goal:
Assemble the final PPT from images and notes.

Action:
```bash
./skill.sh --step assemble --project-dir PPT/<project_id>
```

Output:
- `PPT/<project_id>/deck/deck.pptx`

Done when:
- `deck.pptx` exists
- slides use full-screen images
- speaker notes are present for the generated pages

## Blocker handling

Use this order:

1. If config or credentials are missing, report the exact missing item and stop.
2. If a command fails, preserve the structured JSON error and report the concrete blocker.
3. If a manual artifact is missing or weak, repair it directly and continue.
4. If a generated artifact is invalid, rerun only the minimum necessary step.
5. Do not inspect code unless one of the cases above happens.

## What to report back

Keep the response short and operational. Include:

- completed step
- changed artifact
- current state or next step
- blocker, if any

## Quick references

- Thin entry: `skill.sh`
- Dispatcher: `scripts/execute_step.py`
- Outline path: `PPT/<project_id>/outline/outline.md`
- Plan path: `PPT/<project_id>/plan/plan.json`
- Draft path: `PPT/<project_id>/draft/slide_draft.json`
- Screen text path: `PPT/<project_id>/prompts/screen_text.json`
- Prompt path: `PPT/<project_id>/prompts/prompts.json`
- Asset manifest: `PPT/<project_id>/assets/manifest.json`
- Final deck: `PPT/<project_id>/deck/deck.pptx`
