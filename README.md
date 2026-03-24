# Claw-assistant

## 仓库定位

`Claw-assistant` 现在是一个专门用于 `PPT production workflow`（PPT 制作工作流）的 `openClaw repository`（openClaw 工作流仓库），不再是通用 `tooling repository`（工具仓库）。

这个仓库的目标很单一：

- 定义一条稳定的 `openClaw -> Python programs -> PPT output` 工作流
- 让课程大纲、讲义或文本输入可以被转换为完整的 `PPTX`
- 把状态管理、文案生成、页面规划、图片生成、拼装导出这些环节收敛为同一个专用体系

一句话概括：这个仓库不是“收集各种工具能力”的地方，而是“维护一条专门做 PPT 的 openClaw 工作流”的地方。

## 工作流范围

当前仓库覆盖的主链路是：

```text
project_init
-> outline_ingest
-> slide_draft_generate
-> slide_plan_generate
-> visual_prompt_generate
-> visual_asset_generate
-> ppt_assemble
-> final export
```

其中：

- `openClaw` 负责项目识别、状态读取、步骤推进、用户反馈和局部回退
- `scripts/` 下的程序负责执行具体转换
- `pptflow/` 负责共享 `schema`（数据契约）、`state store`（状态存储）、`OpenAI SDK` 封装、`PPT builder`（PPT 构建器）等基础能力
- `PPT/` 用来承载具体项目的工作区和产物
- `docs/` 用来存放这条工作流的规范、设计和契约文档

## 核心原则

### 1. 这是专用工作流，不是通用工具箱

新增内容必须直接服务于 `PPT workflow`。如果某个模块不能明显提升 PPT 生成、修订、导出或状态管理，就不应该进入这个仓库。

### 2. 先定义契约，再改程序

任何变更都应该先明确：

- 输入是什么
- 输出是什么
- 状态如何推进
- 错误如何表达
- 哪些属于非目标

`docs/` 是正式契约，`scripts/` 和 `pptflow/` 是契约实现。

### 3. openClaw 负责编排，程序负责执行

`openClaw` 应停留在 `orchestration`（编排）层：

- 识别当前项目
- 读取 `state.json`
- 判断下一步该调哪个程序
- 向用户展示中间结果
- 接收反馈并决定回退边界

程序负责做“可执行、可验证、可复跑”的具体动作，不负责代替 `openClaw` 做整条链路决策。

### 4. 所有页面都按统一视觉工作流处理

当前正式设计口径是：

- 所有页面都要生成图片资产
- A/B 的区别是 `prompt strategy`（提示词策略）不同，不是执行路径不同
- 页面规划必须满足 A/B 比例约束，避免退化成全 A 或全 B

### 5. 项目级状态必须显式存储

不同 PPT 项目之间靠 `project workspace`（项目工作区）隔离，而不是靠会话记忆隔离。

每个项目都应在 `PPT/{project_id}/` 下维护自己的：

- `state.json`
- `outline/`
- `draft/`
- `plan/`
- `prompts/`
- `assets/`
- `deck/`
- `exports/`

## 当前目录结构

```text
.
├── README.md
├── CONTRIBUTING.md
├── docs/                 # 工作流 spec、设计文档、契约说明
├── pptflow/              # 共享模块：schema、state、OpenAI SDK、PPT builder
├── scripts/              # 7 个工作流程序 + openClaw 模拟器
├── PPT/                  # 项目工作区与产物目录
├── requirements.txt
└── .env.example
```

更具体地说：

- `docs/`
  - 存放 `PPT workflow spec`、`CLI spec`、`state schema`、程序设计文档
- `pptflow/`
  - 存放共享 `schema`、错误定义、配置加载、JSON 读写、状态管理、PPT 构建逻辑
- `scripts/`
  - 存放工作流入口程序：
    - `project_init.py`
    - `outline_ingest.py`
    - `slide_draft_generate.py`
    - `slide_plan_generate.py`
    - `visual_prompt_generate.py`
    - `visual_asset_generate.py`
    - `ppt_assemble.py`
    - `openclaw_simulator.py`
- `PPT/`
  - 每个子目录对应一个实际项目工作区和生成产物

## 运行方式

建议先激活环境：

```bash
source venv/bin/activate
```

最常见的两类运行方式：

1. 单步运行某个程序

```bash
python scripts/project_init.py --help
python scripts/slide_plan_generate.py --help
```

2. 跑一次端到端模拟

```bash
python scripts/openclaw_simulator.py --project-id demo-001 --overwrite
```

## 文档约束

如果你要改这个仓库，优先看 `docs/`，不要凭记忆修改行为。

尤其是这些文档：

- `PPT-workflow-spec`
- `PPT-assistant-skill`
- `CLI-spec`
- `state-json-schema`
- `Python-programs-详细设计`

如果实现和文档冲突，默认认为仓库进入了不健康状态，应该尽快收敛到一致口径。

## 非目标

这个仓库当前明确不做：

- 通用多领域工具平台
- 与 PPT 无关的能力沉淀
- 长生命周期在线服务
- 复杂多租户系统
- 为未来未知场景预埋重型抽象

## 健康标准

衡量这个仓库是否健康，主要看四件事：

- 能否稳定跑通从输入到 `PPTX` 的完整链路
- 项目状态是否可读、可追踪、可回退
- 文档契约和程序行为是否一致
- 失败时是否能快速定位到具体阶段和具体程序

只要这四件事成立，这个仓库就在朝正确方向演化。
