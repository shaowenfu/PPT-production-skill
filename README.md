# Agent-PPT-Production 🚀

**生产级 AI PPT 自动化创作工具集与工作区**

[![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://github.com/shaowenfu/agent-PPT-production)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`Agent-PPT-Production` 是一个专为 AI Agent（如 openClaw, Claude Code, Gemini CLI）设计的端到端 PPT 创作辅助系统。它不只是一个工具箱，而是一套完整的**生产级工作流解决方案**，旨在将粗糙的原始大纲转化为具备专业深度文案与极致视觉表现力的 `PPTX` 文件。

---

## 🌟 核心特性

- **显式环境约束 (Explicit Environment Contract)**：要求显式使用 `venv`，缺少环境时快速失败，不做静默安装。
- **状态机驱动 (State-Driven)**：每个项目拥有独立的 `state.json` 存盘点，支持流程的断点续传与精准回退。
- **视觉导演系统 (Visual Director)**：Step 5 同时产出 `screen_text.json` 和 `prompts.json`，把用户确认的上屏文字与机器使用的图像提示词分开。
- **原子化脚本 (Atomic Scripts)**：流程解耦为 7 个独立可验证的 Python 脚本，易于 Agent 调用与人工调试。
- **平台薄入口 (Thin Skill Entry)**：通过 `skill.sh` 和 `scripts/execute_step.py` 对外暴露稳定入口，不把业务流程封成黑盒。
- **生产级 Skill 指南**：根目录 `SKILL.md` 定义了 Agent 执行的标准 SOP。

---

## 🛠️ 工作流全景图

本项目严格遵循 **Research -> Plan -> Design -> Produce** 的专业链路：

1.  **Project Init**: 初始化工作区，确立项目 ID。
2.  **Outline Ingest**: 提取/导入深度业务大纲。
3.  **Slide Planning**: 生成 25 页逻辑规划（A/B 类页面分布）。
4.  **Deep Content Generation**: 分批扩写 200-400 字的专业业务内容。
5.  **Visual Prompt Design**: 同时蒸馏最终上屏文字与导演级图像生成提示词，便于用户逐页确认。
6.  **Visual Asset Generate**: 默认调用 Google 图像大模型批量渲染视觉资产，可切回 Doubao。
7.  **PPT Assemble**: 将所有资产封装为最终的 `.pptx`。

---

## 📂 目录结构

```text
.
├── docs/                 # 设计契约与补充文档
├── SKILL.md              # 仓库根技能入口
├── pptflow/              # 核心库：Schema 定义、状态管理、PPT 构建引擎
├── scripts/              # 7 个原子化执行脚本
├── PPT/                  # 项目工作区（Workspace）：存放每个 PPT 的中间产物
├── requirements.txt      # 依赖清单
└── .env.example          # 环境变量模板（Google 默认，DeepSeek / Ofox 可选）
```

---

## 🚦 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/shaowenfu/agent-PPT-production.git
cd agent-PPT-production
```

### 2. 环境配置
建议使用虚拟环境以保证依赖隔离：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 配置秘钥
将 `.env.example` 复制为 `.env` 并填入你的 API Key：
- `GOOGLE_API_KEY`: 默认用于文本生成与图像生成。
- `DEEPSEEK_API_KEY`: 可选，用于文本生成 fallback。
- `OFOX_API_KEY`: 可选，用于图像生成 fallback（火山引擎 Doubao）。

### 4. 平台入口
固定 `aspect ratio` 为 `16:9`。默认 Google 图像生成请求 `image_size="2K"`。

```bash
./skill.sh --step init --project-dir PPT/demo
./skill.sh --step draft --project-id demo --page-ids p1,p2
```

---

## 🤖 对 Agent 的指引

如果你是一个正在阅读本仓库的 Agent：
1.  **阅读 Skill**：请立即阅读 `SKILL.md`，这是你执行任务的最高准则。
2.  **激活环境**：在执行任何脚本前，务必使用 `source venv/bin/activate`。
3.  **状态先行**：每一步执行后，请检查 `state.json` 是否正确更新，这是你“存盘”的唯一凭证。
4.  **逐步确认**：从 `outline` 开始，每一步产出后都先让用户确认中间文件；Step 5 优先给用户看 `prompts/screen_text.json`，不要默认展示完整 prompt。

---

## 🤝 开源贡献

本项目处于活跃开发期，我们非常欢迎以下方向的贡献：
- **布局模型优化**：完善 `pptflow/ppt_builder.py`，支持更多复杂的排版样式。
- **视觉策略增强**：在 `scripts/visual_prompt_design.py` 中引入更多艺术风格预设。
- **多模型支持**：适配更多国产或国际主流大模型接口。

请参考 `CONTRIBUTING.md`（即将上线）了解详细流程。

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 协议。

---

**由 AI 为 AI 打造，开启 PPT 自动化的生产力革命。**
