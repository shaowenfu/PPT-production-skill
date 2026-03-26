# Contributing to Agent-PPT-Production 🚀

感谢你关注 `Agent-PPT-Production`！本项目致力于打造最稳定、最专业的 AI Agent PPT 创作工作流。作为一个开源项目，我们欢迎所有旨在提升 PPT 生产力、优化视觉效果或增强平台兼容性的贡献。

---

## 🎯 我们的原则

在提交 PR 之前，请确保你的改动符合以下核心原则：

1.  **Agent 优先 (Agent-First)**：所有工具和脚本必须易于被 AI Agent 调用（清晰的 CLI 参数、结构化的 JSON 输出）。
2.  **环境自愈 (Self-Healing)**：代码应尽量减少对特定本地环境的依赖，支持虚拟环境（venv）一键部署。
3.  **视觉审美红线 (Artistic Integrity)**：生成的图片必须保持高水准，严禁出现“AI生成”字样、水印或无意义字符。
4.  **契约高于实现 (Contract Over Implementation)**：修改逻辑前，必须先更新 `docs/` 下的相关协议与 Schema。

---

## 🛠️ 建议的贡献方向

我们特别欢迎以下方面的改进：

- **视觉导演进化**：优化 `visual_prompt_design.py` 中的提示词策略，引入更多艺术流派。
- **布局引擎增强**：在 `pptflow/ppt_builder.py` 中增加对图表、多栏排版、复杂图形的支持。
- **平台适配**：改进对 `skill.sh`、`ClawHub` 或 MCP 协议的兼容性。
- **鲁棒性提升**：增强错误处理逻辑，提供更详细的故障诊断 JSON 摘要。

---

## 📋 提交前的自检清单 (Checklist)

提交代码前，请在本地完成以下验证：

- [ ] **环境验证**：确保在 `source venv/bin/activate` 环境下，所有依赖已同步至 `requirements.txt`。
- [ ] **语法检查**：运行 `python -m py_compile scripts/*.py pptflow/*.py` 确保无语法错误。
- [ ] **端到端测试**：使用 `scripts/openclaw_simulator.py` 或手动跑通完整流程，验证 `state.json` 的流转是否正常。
- [ ] **JSON 契约检查**：验证脚本输出的 `stdout` 是否为标准的 JSON 格式，且符合 `docs/` 定义的 Schema。
- [ ] **文档同步**：如果修改了 CLI 参数或状态机逻辑，必须同步更新 `docs/PRODUCTION_PPT_SKILL.md`。

---

## 📜 编码规范

1.  **路径处理**：严禁使用绝对路径。统一使用 `Path(__file__).resolve()` 及其派生路径。
2.  **错误处理**：禁止静默吞掉错误（Silent Fail）。所有异常必须捕获并转化为 `pptflow.errors` 中定义的错误类型。
3.  **日志规范**：
    - `stdout`: 仅输出最终的 JSON 结果摘要。
    - `stderr`: 输出调试信息、进度条和非结构化日志。
4.  **Type Hinting**: 建议为所有新函数增加 Python 类型注解，提升代码可维护性。

---

## 🤝 参与流程

1.  **Fork** 本仓库并创建你的功能分支。
2.  **编写/修改代码**，并同步更新测试用例与文档。
3.  **提交提交 (Commit)**：推荐使用语义化提交信息（如 `feat: add support for chart layout`, `fix: handle deepseek api timeout`）。
4.  **发起 PR**：请在描述中简要说明改动的目的、影响范围及验证方法。

---

**让我们一起定义 AI 时代的 PPT 生产力标准！**
