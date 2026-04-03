# OPENCLAW Start

当 openClaw 第一次拉取本仓库后，必须先读取本文件，并完成以下启动准备。**在这 3 项完成之前，不要进入 PPT 工作流，不要开始生成任何项目。**

## 仓库绝对路径

本仓库在当前机器上的绝对路径是：

`/home/sherwen/work/assistant`

后续如果需要定位 `SKILL.md`、`skill.sh`、`PPT/`、`scripts/` 等路径，统一以这个绝对路径为准。

## 1. Python 环境准备

在仓库根目录完成以下动作：

```bash
python -m venv venv
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

要求：

- 如果 `venv/` 已存在，直接激活并继续安装依赖。
- 如果依赖安装失败，立即停止，并向用户报告具体错误。

## 2. Google API Key 准备

必须向用户索取 `GOOGLE_API_KEY`，然后在仓库根目录创建并写入 `.env` 文件。

最少需要写入：

```env
GOOGLE_API_KEY=<user_provided_key>
```

要求：

- 如果 `.env` 不存在，就创建。
- 如果 `.env` 已存在但缺少 `GOOGLE_API_KEY`，就补写。
- 如果用户还没有提供 `GOOGLE_API_KEY`，立即停止，并明确要求用户提供。

## 3. System Skill 准备

必须完成以下动作：

- 复制当前仓库根目录下的 `SKILL.md`
- 将复制后的文件注册安装为 openClaw 的 `system skill`
- 在复制后的 `system skill` 文档中补充当前机器上的仓库绝对路径：

```text
仓库绝对路径：/home/sherwen/work/assistant
```

要求：

- 这里补充的是**本仓库在当前机器上的绝对路径**，不是 skill 安装目录。
- 完成注册后，后续执行 PPT 工作流时，必须以这个已安装的 `system skill` 为准。

## 4. 创建定期拉取仓库和更新skill的定时Cron Job
为了确保 openClaw 能够及时获取到本仓库的更新内容，需要在系统中设置一个定时任务，定期拉取仓库最新代码并更新 `system skill`。可以使用 `cron` 来实现这一功能。每天凌晨 2 点执行该cron job：拉取仓库最新代码，并检查更新，判断是否需要更新 `system skill` 。

## 完成标准

只有在以下 3 项都完成后，才能继续：

1. `venv` 可激活，依赖已安装完成
2. `.env` 已存在，且包含有效的 `GOOGLE_API_KEY`
3. `SKILL.md` 已复制并注册为 openClaw 的 `system skill`，且其中已写入仓库绝对路径

完成后，再回到仓库根目录，继续阅读 `SKILL.md` 并进入正式工作流。
