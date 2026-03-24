# PPT Python Programs 详细设计

## 设计目标
- **极简主义**：删除所有不必要的解析器和规划器。
- **Agent 核心**：高层逻辑（如规划 A/B 类）全部由 Agent 完成，脚本只接受 ID。
- **图像即页面**：PPTX 仅作为图片的全屏容器。

## 核心程序流

### 1. `project_init.py`
- 初始化 `PPT/{project_id}/` 子目录（outline, draft, plan, prompts, assets, deck）。
- 建立初始 `state.json`。

### 2. `slide_draft_generate.py`
- **输入**：`--page-ids`。
- **模型**：使用 `OPENAI_API_KEY` 下配置的模型（默认 gemini-flash）。
- **逻辑**：分批次向大模型请求“知识全集”。
- **产物**：`draft/slide_draft.json`。

### 3. `visual_asset_generate.py`
- **集成**：阿里云 DashScope (Qwen-Image-2.0-pro)。
- **逻辑**：
    - 读取 `prompts.json`。
    - 调用阿里云 API 生成图片。
    - 下载并保存为 `assets/{page_id}.png`。
    - 输出 `manifest.json`。

### 4. `ppt_assemble.py`
- **底层**：基于 `ppt_builder.py` 极简封装。
- **逻辑**：
    - 读取 `manifest.json`。
    - 遍历图片，将每张图插入一张幻灯片并设为满屏。
    - 产物：`deck/deck.pptx`。

## 公共模块 `pptflow/`
- `state_store.py`: 负责状态机的持久化。
- `openai_client.py`: 负责文本侧的 OpenAI 接口请求。
- `ppt_builder.py`: 极简幻灯片构造，仅包含 16:9 页面创建与背景图插入逻辑。
