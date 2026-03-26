# Agent-PPT-Production 平台收尾清单

本文档只定义 `skill.sh MVP` 所需的最小平台适配，不再把“平台包装”扩展成“产品重构”。

## 目标

- [x] 保留现有原子脚本，不把业务逻辑收口成黑盒。
- [x] 提供稳定的 `stdout JSON / stderr log` 契约。
- [x] 提供稳定的 `error_code` 与路径解析行为。
- [x] 提供一个很薄的统一入口 `scripts/execute_step.py`。
- [x] 提供仓库根入口 `skill.sh` 和平台元数据 `platform/skill.yaml`。

## 当前约束

- [x] `aspect ratio` 固定为 `16:9`。
- [x] 图像尺寸固定为 `1792x1024`。
- [x] 不引入 `tool_manifest.json`。
- [x] 不在运行时做 `jsonschema` 校验。
- [x] 不做自动安装依赖、自愈式修改环境。

## 已完成

### Runtime

- [x] `pptflow/cli.py` 统一输出 JSON summary。
- [x] 所有人类日志写入 `stderr`。
- [x] `pptflow/errors.py` 提供可枚举错误码。

### Path & Entry

- [x] `scripts/_bootstrap.py` 统一脚本引导。
- [x] `pptflow/paths.py` 统一路径解析。
- [x] `scripts/execute_step.py` 只做参数转发、路径归一化和子进程 JSON 透传。
- [x] `skill.sh` 作为平台默认入口。

### LLM Hardening

- [x] `pptflow/llm_json.py` 处理 `code fence`、尾逗号、简单截断和前后缀文本。

### Verification

- [x] `stdout` 纯 JSON 行为已测试。
- [x] `LLM JSON` 容错已测试。
- [x] 跨 `cwd` 的 `project_init` 冒烟已验证。

## Non-goals

- [x] 不做多 `aspect ratio` 支持，固定 `16:9 (1792x1024)`。
- [x] 不引入 `tool_manifest.json` 和完整工具级 `schema`。

## Deferred

- [ ] 完整上游链路的生产级回归套件。
- [ ] 视觉 Prompt 输出中的 `refined_text` 持久化。

## 验收标准

- [x] 任意工作目录下可调用 `skill.sh`。
- [x] 成功时 `stdout` 只输出一个合法 JSON 对象。
- [x] 失败时返回稳定 `error_code`。
- [x] 平台入口不引入第二套业务契约系统。
