# Agent-PPT-Production 平台适配规范

本文档定义如何将当前项目从“本地脚本工作流”改造为“可被平台稳定调用的 Agent Skill / Tooling”。主要适配目标为 `skill.sh` 与 `ClawHub` 一类平台。

目标不是重写流程，而是收敛出稳定的 `runtime contract`、`tool contract` 与 `packaging contract`，让现有工作流在跨平台环境下可预测、可恢复、可调试。

## 一、设计原则

- [ ] 保留现有原子脚本边界，不把业务流程收口成一个黑盒。
- [ ] 平台适配优先做契约，不优先做文档包装。
- [ ] `stdout` 只输出机器可读 JSON，所有人类日志统一写入 `stderr`。
- [ ] 禁止静默副作用：不自动安装依赖，不自动修改用户环境，不吞错。
- [ ] 所有平台相关能力都必须通过显式 `schema`、显式 `error_code` 和显式 `artifact` 暴露。

## 二、改造范围

### In Scope

- [ ] 统一脚本输入输出契约。
- [ ] 统一错误码与环境检查行为。
- [ ] 抽取路径解析与运行时上下文。
- [ ] 为平台补充 `skill.yaml` 与工具清单文件。
- [ ] 增强 LLM JSON 输出容错与回归测试。
- [ ] 增加宽高比 `aspect ratio` 支持，并贯穿到生成与组装链路。

### Non-goals

- [ ] 不新增浏览器 UI。
- [ ] 不引入“自动安装依赖”的自愈逻辑。
- [ ] 不把资产清单与平台清单复用为同一个 `manifest.json`。
- [ ] 不为了平台适配而重写现有内容生成 / 图像生成核心逻辑。

## 三、Phase 1：Runtime Contract

### 3.1 脚本入口策略

- [ ] 保留现有原子脚本作为真实执行入口。
- [ ] 可新增一个很薄的 `scripts/execute_step.py` 作为平台友好入口，但它只负责：
  - 参数标准化
  - 路径解析
  - 分发到具体脚本
  - 汇总统一返回格式
- [ ] `execute_step.py` 不得承载业务逻辑，不得替代原子脚本的独立可执行性。

### 3.2 标准输出约束

- [ ] 所有脚本统一复用 [pptflow/cli.py](/home/sherwen/work/assistant/pptflow/cli.py) 的 JSON summary。
- [ ] `stdout` 中只能出现一个合法 JSON 对象。
- [ ] `print()` 产生的进度日志全部迁移到 `stderr`。
- [ ] 成功响应必须至少包含：
  - `ok`
  - `tool`
  - `project_id`
  - `project_dir`
  - `artifacts`
  - `metrics`
  - `warnings`
- [ ] 错误响应必须至少包含：
  - `ok`
  - `tool`
  - `error.code`
  - `error.message`
  - `error.details`
  - `error.exit_code`

### 3.3 错误语义

- [ ] 在 [pptflow/errors.py](/home/sherwen/work/assistant/pptflow/errors.py) 基础上细化平台可分支处理的 `error_code`。
- [ ] 至少补齐以下错误：
  - `NEEDS_CONFIG`
  - `MISSING_API_KEY`
  - `INVALID_ENV`
  - `INVALID_JSON_OUTPUT`
  - `UPSTREAM_TIMEOUT`
  - `UPSTREAM_BAD_RESPONSE`
- [ ] 错误信息对外稳定，对内可通过 `details` 携带必要上下文。
- [ ] 禁止仅靠自然语言提示表达错误类别。

### 3.4 环境检查

- [ ] 保留“显式激活 `venv`”的使用方式。
- [ ] 若缺少 `venv` 或缺少依赖，应快速失败并返回 `ENVIRONMENT_ERROR` / `NEEDS_CONFIG`，附修复指引。
- [ ] 不允许运行时静默 `pip install`。

## 四、Phase 2：Path & Config Contract

### 4.1 路径解析

- [ ] 新增统一 `Path Resolver`，集中处理仓库根目录、项目目录和相对路径转绝对路径。
- [ ] 删除各脚本内重复的根目录注入逻辑，避免多处维护。
- [ ] 清理文档、脚本、配置中的硬编码绝对路径，如 `/home/sherwen/...`。
- [ ] 所有项目工件路径在 JSON summary 中统一使用相对 `project_dir` 的路径表达。

### 4.2 配置加载

- [ ] 在 [pptflow/config.py](/home/sherwen/work/assistant/pptflow/config.py) 中把“读取配置”和“校验配置”拆开。
- [ ] 校验失败时，返回稳定的 `error_code`，并给出缺失项列表。
- [ ] API Key 缺失时，统一返回 `NEEDS_CONFIG`，而不是仅抛泛化异常。
- [ ] 配置摘要中允许暴露“是否已配置”，禁止回显密钥值。

### 4.3 宽高比支持

- [ ] 将 `aspect ratio` 作为正式契约字段，而不是仅做脚本参数。
- [ ] 至少支持：
  - `16:9`
  - `4:3`
  - `9:16`
- [ ] 该字段必须贯穿：
  - 配置默认值
  - 计划 / Prompt 输入
  - 图像生成尺寸映射
  - PPT 页面尺寸设置
- [ ] 禁止只在 CLI 层加参数但内部仍固定写死 `16:9`。

## 五、Phase 3：Tool Contract

### 5.1 工具清单

- [ ] 为每个可平台调用的脚本定义独立工具契约。
- [ ] 建议覆盖：
  - `project_init`
  - `slide_draft_generate`
  - `visual_prompt_design`
  - `visual_asset_generate`
  - `ppt_assemble`

### 5.2 输入 Schema

- [ ] 每个工具必须声明最小输入集合。
- [ ] 参数名保持稳定，避免同义词并存。
- [ ] 典型输入字段包括：
  - `project_dir`
  - `project_id`
  - `page_ids`
  - `target_pages`
  - `overwrite`
  - `batch_size`
  - `aspect_ratio`

### 5.3 输出 Schema

- [ ] 每个工具的 JSON summary 中必须稳定声明产物和核心指标。
- [ ] `artifacts` 只列实际产出的文件。
- [ ] `metrics` 只放可枚举、可比较的指标，不混入自然语言说明。

### 5.4 资产清单与平台清单分离

- [ ] 保留 `assets/manifest.json` 作为资产清单。
- [ ] 平台元数据禁止复用该文件名。
- [ ] 建议新增：
  - `platform/skill.yaml`
  - `platform/tool_manifest.json`

## 六、Phase 4：LLM Output Hardening

### 6.1 统一 JSON 容错层

- [ ] 为 LLM 输出新增统一的 `JSON Normalizer`。
- [ ] 至少处理以下场景：
  - 多余前后缀文本
  - 代码块包裹
  - 尾逗号
  - 局部截断
  - 顶层类型错误
- [ ] 修复失败后再进入 `Pydantic schema` 校验。

### 6.2 Prompt Contract

- [ ] 将视觉生成中的负向约束内置到 [scripts/visual_prompt_design.py](/home/sherwen/work/assistant/scripts/visual_prompt_design.py)。
- [ ] 平台调用方不需要再手动追加“去 AI 痕迹”提示词。
- [ ] 提示词输出结构必须区分：
  - `prompt`
  - `refined_text`
  - `page_id`

## 七、Phase 5：Packaging

### 7.1 `skill.yaml`

- [ ] 新增 `platform/skill.yaml`，用于描述技能元数据。
- [ ] 至少包含：
  - 名称
  - 版本
  - 描述
  - 仓库地址
  - 必需环境变量
  - 默认入口

### 7.2 `tool_manifest.json`

- [ ] 新增 `platform/tool_manifest.json`，用 JSON Schema 描述每个工具的输入输出。
- [ ] 每个工具需声明：
  - `name`
  - `description`
  - `input_schema`
  - `output_schema`
  - `artifacts`
  - `error_codes`

### 7.3 平台文档

- [ ] `README-ClawHub.md` 只做平台快速开始，不重复主 README。
- [ ] `docs/SECURITY_AUDIT.md` 应明确：
  - 不回传用户密钥
  - 不记录敏感输入到公开日志
  - 上游模型调用边界

## 八、Phase 6：Robustness Testing

### 8.1 最小回归集

- [ ] `stdout` 纯 JSON 测试。
- [ ] 缺失环境变量测试。
- [ ] 缺失依赖快速失败测试。
- [ ] 跨工作目录执行测试。
- [ ] 断点续传测试。
- [ ] 资产清单恢复测试。

### 8.2 LLM 容错测试

- [ ] 模拟带尾逗号的 JSON。
- [ ] 模拟被 Markdown code fence 包裹的 JSON。
- [ ] 模拟截断 JSON。
- [ ] 模拟字段缺失或字段类型错误。

### 8.3 宽高比测试

- [ ] 分别验证 `16:9`、`4:3`、`9:16` 的图像生成尺寸映射。
- [ ] 验证 PPT 页面尺寸与图像尺寸策略一致。

## 九、实施顺序

- [ ] 先做 `Runtime Contract`。
- [ ] 再做 `Path & Config Contract`。
- [ ] 再做 `Tool Contract` 与 `Packaging`。
- [ ] 最后做 `LLM Hardening` 与完整回归测试。

## 十、验收标准

- [ ] 任一工具都可在任意工作目录下被稳定调用。
- [ ] 任一工具执行成功时，`stdout` 都只输出合法 JSON summary。
- [ ] 任一工具执行失败时，平台可根据 `error_code` 做分支处理。
- [ ] 缺失配置时返回 `NEEDS_CONFIG`，而不是模糊报错。
- [ ] 平台元数据文件与业务资产清单完全解耦。
- [ ] 三种 `aspect ratio` 至少完成端到端链路验证。

