# 从这里安装 Weekly Highlights 1.01

这是可下载到本机的技能和脚本，不是云端代运行服务。适用于有本地文件/命令和图片输入能力的Codex、Pi、WorkBuddy、TRAE、OpenClaw等agent。不要把拖入压缩包等同于已完成配置。

给agent仓库链接后可直接说：

> 请安装这个仓库中的weekly-highlight-workflow 1.01。先读START_HERE.md及SKILL.md。询问我本机的数据工作目录，确认沿用已有ACP/PNAS历史Word还是新建空库；从当前客户端可用模型中选便宜执行模型。实际将两张随机测试图片送入这个模型，核验视觉结果；没有视觉能力则记录失败，向我说明并配置通过测试的视觉审阅者。不要拷贝仓库作者的路径或账号，不要绕过PDF权限。完成后报告配置路径、实际模型、视觉测试、依赖与历史读取状态。

## 1. 下载与检查

下载GitHub版本标签对应的源码/Release压缩包，解压后找到有SKILL.md的目录。先查看脚本，再用已安装Python运行：

```text
python scripts/install_share.py --platform codex --verify-only
python scripts/install_share.py --platform codex
```

可替换platform为pi、trae、openclaw。`--destination`可明确指定最终技能目录（目录名为weekly-highlight-workflow）；WorkBuddy优先使用客户端ZIP导入，命令安装必须指定该客户端实际显示的技能目录，不猜路径。目标已存在会停止；确认升级才用`--replace-existing`，旧版被移入独立备份目录。当前已有另一目录同名技能时先检查优先级，避免同时加载两个版本。

## 2. 配置数据路径

请让agent先收集工作目录和可用模型，使用下面字段运行；尖括号需替换为本人实际值，不可原样执行：

```text
python scripts/setup_share.py configure --workspace <本人已存在的工作根目录> --platform <客户端> --worker-model <实际可用的小模型ID>
```

若从零开始，加`--new-library`，创建仅有标题的ACP/PNAS空库，**不会塞入示例论文**；已有任一目标Word则拒绝覆盖。已有历史路径不同，用`--acp-docx`和`--pnas-docx`，二者必须在选定工作根目录内。若提供自定义Word，其五段格式需通过校验；未知格式不自动重排。

配置写在本人工作目录`.weekly-highlights/config.json`，升级技能不覆盖它。可写的技能目录只保存本地指针installation.local.json；技能目录只读时，用各脚本`--config`，或设WEEKLY_HIGHLIGHTS_CONFIG。优先级为显式参数、该环境变量、当前目录祖先的本地配置、安装指针。不要把本地配置、指针、凭证和测试记录提交GitHub。

需要Python 3.10+及requirements.txt中的包、LibreOffice、Poppler/pdftoppm。已有工具可通过`--soffice`、`--pdftoppm`配置；运行doctor检查。脚本不会替用户安装软件或变更系统设置。

## 3. 实测模型视觉能力

```text
python scripts/vision_probe.py make --config <本地config.json> --output-dir <全新测试目录>
```

让选定小模型**实际打开两张PNG**，按PROMPT.txt回答；不能读取answer.private.json或OCR代答。将实际回答和图片工具证据存response.json：

```text
python scripts/vision_probe.py grade --challenge <测试目录/challenge.json> --response <response.json> --output <capability.json>
python scripts/setup_share.py finish --config <本地config.json> --capability <capability.json>
```

只有实际图片输入、模型匹配及全部图像题通过才ready。更换视觉审阅模型使用`setup_share.py models`，重新make/grade；若改用主模型，finish需`--fallback-confirmed --worker-capability <小模型实际测试记录>`。不可用的测试如实记录，不能伪造pass。不另要求API密钥，优先使用当前agent已有连接。

## 4. 开始使用

说“帮我做一次Weekly Highlights”。第一版清单已经去重；审核后明确继续，再下载和更新Word。命令格式、输入schema和失败处理见references。跨平台说明是兼容设计，未经真实客户端运行的平台不能声称已验收。GitHub托管代码，不提供机构论文访问权限。
