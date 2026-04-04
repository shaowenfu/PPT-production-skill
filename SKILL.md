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

## Prerequisites

Keep this short checklist in mind before running the workflow:
- use **Python 3.11** and create `venv/`
- activate the environment and run `pip install -U pip setuptools wheel && pip install -r requirements.txt`
- create `.env` and set at least `GOOGLE_API_KEY`
- run `./skill.sh --help` and a minimal `init` once before first real project

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
12. Before touching any project under `PPT/`, read `PPT/README.md`.
13. `PPT/README.md` is the project registry for the whole `PPT/` workspace. It records brief `start` / `finish` history for every project.
14. Default to the current user-specified `project_id` only. Do not inspect or modify historical project directories unless the user explicitly asks to continue or review them.
15. When starting a new project, append one `start` record to `PPT/README.md`.
16. When finishing a project, append one `finish` record to `PPT/README.md`.
17. If one user request must be split into several PPT sub-projects, register them first in the `Project Queue` section of `PPT/README.md`.
18. Only one sub-project may be `IN_PROGRESS` at a time. By default, work only on the current `IN_PROGRESS` item unless the user explicitly changes priority.

## Default execution policy

- Always start with `Step 0: Scope Gate`. Do not jump straight into the workflow.
- If the requested deck is estimated to be more than `30` pages, do not produce it as one project. Split it into modules first, get user confirmation, then run one module at a time.
- Use the workflow flexibly based on input maturity. Do not mechanically force every project through the exact same path.
- If the user has already provided concrete page-by-page content, treat that content as the source of truth. You may still use the existing workflow, but do not let `outline` / `draft` rewrite or dilute the fixed page content.
- In fixed-content cases, write the final on-slide copy into `plan.json` using `content_mode="locked"`, `source_text`, `source_origin`, and `copy_locked=true`. Prefer `./skill.sh --step auto` so the workflow can skip Draft automatically.
- Prefer using AI for structure, page-type judgment, and prompt drafting; prefer human-confirmed source content for final on-slide wording.
- After every step, stop for user confirmation before the next step.
- The machine-facing artifact stays in its original format (`.md` / `.json`).
- The user-facing review artifact must be converted manually into a `.txt` file and sent to the user as a file.
- Do not use a normal chat message as a substitute for the `.txt` file.
- The review file should keep the original basename and only change the suffix to `.txt`.
- If the user edits the approved text, update the machine-facing artifact before continuing.
- Only stop automatically on real blockers:
  - missing source material
  - missing credentials
  - command failure
  - invalid or missing required artifact

## Script responsibility table

| Step | Backing mode | What it does | Scope |
| --- | --- | --- | --- |
| `init` | script | creates workspace and state files | one project |
| `auto` | script | routes to the next required step and skips Draft for locked-copy pages | one project or selected pages |
| `draft` | script | generates deep page content into `draft/slide_draft.json` | only requested `page_ids` |
| `prompt` | script | generates user-reviewable screen text plus visual prompts from draft content | supports full run, selected pages, and parallel batches |
| `assets` | script | generates slide images from prompts | supports full run, selected pages, and parallel generation |
| `assemble` | script | packs images into `deck.pptx` and writes notes | one final deck |

Manual steps:

- `outline` is direct agent writing
- `plan` is direct agent writing

## Workflow

### Step 0: Scope Gate

Goal:
Confirm scope before entering the workflow.

Action:
- estimate the requested page count
- if page count `> 30`, split into modules first
- if it is split into multiple child PPT projects, register them in `PPT/README.md` `Project Queue`, mark only one as `IN_PROGRESS`, and execute them one by one
- write the global scope plan in `PPT/<project_id>/scope/global_plan.txt`

Done when:
- the scope is clear
- the user has confirmed the module split or approved a `<= 30` page scope
- for multi-project work, `Project Queue` in `PPT/README.md` has been updated before Step 1 starts

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
- `PPT/<project_id>/outline/outline.txt`

Done when:
- the outline is in Simplified Chinese
- the structure is coherent and presentation-ready
- the chapter flow matches the user goal
- convert `outline/outline.md` into `outline/outline.txt`
- send `outline/outline.txt` to the user as a file

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
- `PPT/<project_id>/plan/plan.txt`

Done when:
- `project_id` is present at the top level of `plan.json`
- page count is `25` by default unless the user says otherwise
- `page_id` is unique and sequential like `p1`, `p2`, `p3`
- `category` uses only `A` or `B`
- `B` pages stay within `20%-40%`
- every page has a deliberate `layout_type`
- convert `plan/plan.json` into `plan/plan.txt`
- send `plan/plan.txt` to the user as a file

Planning rules:
- decide `layout_type` in `plan.json`, not later in prompt generation
- `layout_type` should express information structure, not visual style keywords
- if the user already fixed the final on-slide wording for a page, set `content_mode` to `locked`, fill `source_text`, and set `copy_locked=true`
- if a page still needs AI content expansion, keep `content_mode` as `generated` and provide `content_hint`
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

Minimal schema example:
```json
{
  "project_id": "<project_id>",
  "pages": [
    {
      "page_id": "pN",
      "title": "页面标题",
      "category": "A",
      "layout_type": "bullet_points",
      "content_mode": "generated",
      "content_hint": "页面内容提示",
      "source_text": null,
      "source_origin": null,
      "copy_locked": false
    }
  ],
  "target_b_ratio": 0.3,
  "actual_b_ratio": 0.3,
  "metadata": {}
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
- `PPT/<project_id>/draft/slide_draft.txt`

Done when:
- requested pages exist in `slide_draft.json`
- content is substantive, not just title restatement
- convert `draft/slide_draft.json` into `draft/slide_draft.txt`
- send `draft/slide_draft.txt` to the user as a file

### Step 5: Visual Prompt Design

Goal:
Convert slide draft content into user-confirmable on-slide text and image-generation prompts.

Fixed-copy rule:
- if `content_mode="locked"`, `prompt` step must reuse `source_text` exactly and must not rewrite it
- `draft/slide_draft.json` is optional for locked pages

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
- `PPT/<project_id>/prompts/screen_text.txt`

Done when:
- `screen_text.json` exists
- `prompts.json` exists
- requested pages are present in `screen_text.json`
- requested pages are present in `prompts.json`
- prompts avoid watermark language and stray rendered text
- convert `screen_text.json` into `screen_text.txt`
- send `screen_text.txt` to the user as a file
- if the user changes the approved text, sync `prompts/prompts.json` before step 6

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
- `PPT/<project_id>/assets/manifest.txt`

Done when:
- requested images exist
- image aspect ratio is `16:9`
- write `assets/manifest.txt`
- send `assets/manifest.txt` and the images to the user

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
- Outline review path: `PPT/<project_id>/outline/outline.txt`
- Plan path: `PPT/<project_id>/plan/plan.json`
- Plan review path: `PPT/<project_id>/plan/plan.txt`
- Draft path: `PPT/<project_id>/draft/slide_draft.json`
- Draft review path: `PPT/<project_id>/draft/slide_draft.txt`
- Scope path: `PPT/<project_id>/scope/global_plan.txt`
- Screen text path: `PPT/<project_id>/prompts/screen_text.json`
- Screen text review path: `PPT/<project_id>/prompts/screen_text.txt`
- Prompt path: `PPT/<project_id>/prompts/prompts.json`
- Asset manifest: `PPT/<project_id>/assets/manifest.json`
- Asset review path: `PPT/<project_id>/assets/manifest.txt`
- Final deck: `PPT/<project_id>/deck/deck.pptx`
