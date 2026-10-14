---
name: weekly-highlight-workflow
description: "为用户自选期刊与研究领域制作文献周报，也可按给定期刊阅读官网与近期文章后确定筛选范围。首版前历史及跨版本去重，输出可复制审核清单，确认后下载授权PDF并验证更新Word。首次配置本机路径、期刊、领域、模型并实测视觉能力。用于Weekly Highlights、文献周报与技能配置。"
metadata:
  version: "1.11"
  release: "share"
---

# Weekly Highlights 1.11

先读 [START_HERE](START_HERE.md)。没有默认期刊、预印本来源或研究方向；文件导入不等于配置完成。

## 确定使用者的范围

询问数据根目录、目标期刊及领域，核实期刊全名、官网/ISSN和来源，避免同名刊或整个出版社混入。支持一刊或多刊，不沿用作者个人期刊、学科、路径或账号。

用户指定领域时按研究问题、纳入和排除项配置；用户也可给期刊并授权agent自行阅读后找相关内容。后者先联网读取各刊官方Aims & Scope与近期文章，说明筛选范围并保存依据，不能把刊物范围猜成个人狭窄兴趣。综合刊中“相关”仍模糊且会改变结果时询问研究方向；已授权按完整期刊范围或全领域筛选时直接继续，不再设固定确认。预印本只有显式选择来源才纳入。见 [selection-setup](references/selection-setup.md)。

创建本地selection.json，用setup_share.py configure --selection配置。旧用户或变更范围用scope --selection，保留历史与模型设置。选择未完成时不得进入正式流程。

从当前agent可用模型选便宜执行模型。用vision_probe.py make生成随机题，实际将两张PNG送入该模型并grade；模型名称、支持图片声明、OCR或其他模型代答不能作为通过。失败如实记录，经用户同意用另一个实测通过模型做视觉。无法选模的平台测试当前实际模型，不假称委派。换模型/供应方/客户端后重测；细节见 [vision-setup](references/vision-setup.md)。

## 文献周报

筛选读 [screening-profile](references/screening-profile.md) 与本地范围；数据协议读 [workflow-spec](references/workflow-spec.md)。后半程按需读 [execution](references/execution.md)，平台按需读 [platform-adapters](references/platform-adapters.md)。

1. preflight验证选择、视觉测试和全部历史Word。默认上海时区含首尾10天，用户可配置窗口。
2. 每刊使用核实的官网目录/RSS/日期搜索等来源，分页覆盖窗口并记录停止原因。用通用feed/article、经页面核实选择器的index脚本或浏览工具；不声称任意出版社都可自动解析。
3. **首版复制清单之前完成本轮、全部所选期刊历史DOI及可确认跨版本去重，解决相似题名歧义。** 缺失/损坏历史不当空库。未完成去重不输出正式清单。
4. 读拟入选及边界项完整摘要，依据本地领域/声明范围判断问题、增量、具体相关性，不能只看关键词。期刊身份、日期、摘要须核实；受限时可标记使用出版商Crossref/PubMed原始摘要，不能把题名或Significance当摘要。
5. 去重后写中文Summary，prepare-review按实际所选期刊各给一个复制块、分别编号。报告范围、覆盖不足、重复和入选数，不凑篇数。
6. 用户按本修订编号/DOI审核，新增先核验去重；明确授权继续后approve，冻结选择、文章与源历史。选择变更后重做清单。审核前不下载PDF、不建正式日期目录、不改Word。
7. 固定脚本/便宜模型做机械步骤，实测通过模型做视觉。短交接不复制整段聊天，不重选论文或改批准文本。异常升级，不擅自装软件、改全局模型或新增付费API。
8. 核验PDF身份、Word五段、作者、科学记号与历史内容。完整渲染并实际查看新增/交界/变化页；可信同环境且像素完全相同历史页可复用，无基线全检。验证备份后原子安装并比哈希。零新增期刊不改Word。

不编来源或结果，不访问/修改Zotero/EndNote，不绕过权限，不删除旧档；遵守使用者项目归档规则。汇报实际模型、产物、目检/复用页数和失败项。视觉题仅证明基本能力，不保证所有科学页面审校；未逐客户端验收时如实说明。
