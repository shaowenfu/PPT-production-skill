---
name: ppt-production-expert
description: Drive the seven-step AI PPT workflow for this GitHub repository after an agent clones it locally. Use this skill whenever the user wants to create, continue, repair, or fully deliver a PPT project under `PPT/`, including writing `outline/outline.md`, authoring or fixing `plan/plan.json`, generating slide drafts, designing visual prompts, rendering assets, or assembling `deck/deck.pptx`. Also use it whenever the user asks to resume from `state.json`, recover a broken PPT step, or directly produce a final PPT from this repo even if they do not mention the skill by name.
compatibility:
  - git
  - bash
  - python
---

# PPT Production Expert

Use this skill after the agent clones this repository. The workflow has seven steps, but only part of it is script-backed. `outline` and `plan` are usually direct agent work on project artifacts; the later production steps use the repo scripts.

## Operating assumptions

1. Treat the directory containing this `SKILL.md` as the repo root. Resolve all paths relative to that directory. Do not assume any absolute filesystem path.
2. If the repo is not present locally yet, clone it first and then work from the cloned repo root.
3. Before any Python step, bootstrap the environment:
   - if `venv/` does not exist, run `python -m venv venv`
   - run `source venv/bin/activate`
   - run `pip install -r requirements.txt`
4. Keep `aspect ratio` fixed at `16:9`. Use image size `1792x1024`.
5. Prefer the thin entry `./skill.sh` for script-backed steps. It forwards to `scripts/execute_step.py`.
6. Keep atomic script boundaries intact. Do not collapse the workflow into one custom script.
7. When resuming a project, read `PPT/<project_id>/state.json` first and align the next action with the recorded artifacts.
8. Before text or image generation, confirm the required credentials are available:
   - `DEEPSEEK_API_KEY` for text generation
   - `OFOX_API_KEY` for image generation

## Seven-step workflow

### Step 1: Project Init

Use when the user wants a new PPT workspace.

Run:
```bash
./skill.sh --step init --project-dir PPT/<project_id>
```

Expected result:
- `PPT/<project_id>/state.json`
- standard project subdirectories

### Step 2: Outline Ingest

This is direct agent work, not a script.

Write:
- `PPT/<project_id>/outline/outline.md`

Requirements:
- Simplified Chinese
- clear business or technical structure
- usually `7-10` core sections

### Step 3: Slide Planning

This is direct agent work, not a script.

Write:
- `PPT/<project_id>/plan/plan.json`

Requirements:
- conform to `pptflow/schemas.py` `SlidePlanDocument`
- default to `25` pages unless the user says otherwise
- keep `B` pages within `20%-40%`
- make `page_id` unique and sequential

### Step 4: Deep Content Generation

Use after `outline` and `plan` exist.

Run in batches:
```bash
./skill.sh --step draft --project-dir PPT/<project_id> --page-ids p1,p2,p3,p4,p5
```

Validate:
- `PPT/<project_id>/draft/slide_draft.json` exists
- generated pages contain substantive content, not title restatement

### Step 5: Visual Prompt Design

Use after `draft` exists.

Run:
```bash
./skill.sh --step prompt --project-dir PPT/<project_id> --batch-size 5
```

Validate:
- `PPT/<project_id>/prompts/prompts.json` exists
- prompts avoid AI watermark language and stray rendered text

### Step 6: Visual Asset Generate

Use after prompts are ready.

Run:
```bash
./skill.sh --step assets --project-dir PPT/<project_id>
```

Optional:
```bash
./skill.sh --step assets --project-dir PPT/<project_id> --target-pages p8,p9 --overwrite
```

Validate:
- `PPT/<project_id>/assets/manifest.json` exists
- generated images use `1792x1024`

### Step 7: PPT Assemble

Use after assets are ready.

Run:
```bash
./skill.sh --step assemble --project-dir PPT/<project_id>
```

Expected result:
- `PPT/<project_id>/deck/deck.pptx`

## Execution policy

- If the user asks for the full workflow or directly asks for the final PPT, run through all seven steps in order without intermediate approval requests, unless blocked by missing source material, missing credentials, or a hard failure.
- If the user explicitly asks to review prompts, outlines, plans, or other intermediate artifacts, stop after that step and wait.
- If the user asks for only one step, run only that step and validate its prerequisites first.
- If a script-backed step fails, preserve the structured JSON error and explain the concrete blocker.
- If a manual step is missing, create or repair the artifact directly instead of forcing a later script to fail.

## What to report back

Keep the response short and operational. Include:
- what step was completed
- which artifact changed
- current project state or next recommended step
- any blocker that prevents moving forward

## Quick references

- Thin entry: `skill.sh`
- Dispatcher: `scripts/execute_step.py`
- Schemas: `pptflow/schemas.py`
- State handling: `pptflow/state_store.py`
