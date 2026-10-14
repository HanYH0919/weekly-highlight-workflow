# 平台适配

同一SKILL.md与共享脚本，运行配置由收件人生成。安装目录与数据目录是两件事；只读技能安装目录可用显式--config或WEEKLY_HIGHLIGHTS_CONFIG指向本人工作区。技能文件导入不等于完成路径/模型/视觉配置；没有自动钩子时首次使用必须完成setup。

| 平台 | 安装入口 | 模型和图片实测 |
|---|---|---|
| Codex | 标准Agent Skills目录，或显式原生技能目录；openai.yaml只供Codex UI | 可指定子代理时按实际可用模型ID请求，新上下文内实际查看PNG |
| Pi | 标准技能目录或其配置目录；共享.agents/skills可用 | 不假设内置子代理，使用已经安装的委派扩展或选择当前模型后实际送图 |
| TRAE | 原生技能目录；使用.agents/skills需在客户端设置启用 | 用其实际可用选模/子代理/图片工具，不能假定支持特定OpenAI模型 |
| OpenClaw | workspace技能目录、受支持共享目录或导入入口 | 留意Gateway/节点/沙箱文件路径，图片需到达真正执行模型 |
| WorkBuddy | 客户端ZIP导入，或明确其设置显示的技能目录；另提供带其扩展字段的ZIP | 不把CodeBuddy和WorkBuddy目录当同一产品，缺自动选模时当前模型实测 |

原生导入按钮可能只复制技能。此包采用显式安装脚本加首次使用配置，避免依赖各平台未统一的install hook。安装脚本不改全局模型、账户、API密钥或插件配置；重复安装保留本地路径配置并备份旧技能。相同名字在多目录的优先级由客户端控制，安装前检查重复版本。

官方依据（2026-10-14核查）：[Codex Skills](https://learn.chatgpt.com/docs/build-skills)、[Codex子代理](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[Pi Skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)、[TRAE](https://docs.trae.cn/ide_skills)、[WorkBuddy](https://open.workbuddy.cn/docs/skill)、[OpenClaw](https://docs.openclaw.ai/tools/skills)。

这些是格式/流程适配依据，不代表全部客户端已端到端验收。发布验收记录分别列实测和未测项。小模型无视觉能力的回退必须明示，禁止把支持图片的标记或自我陈述作为通过记录。
