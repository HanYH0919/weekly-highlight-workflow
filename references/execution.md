# 机械执行与视觉验收

主模型负责相关性、Summary、用户意图及来源/公式异常。便宜执行模型来自本地配置，不能硬编码某个提供方。视觉审阅者必须有安装时真实通过记录；看图小模型不可用时用已测试主模型回退。没有选模/委派能力的客户端，由明确选定的当前模型调用同一套脚本，不谎称已切换。

短交接只传技能/配置/批准包路径、目标期刊、源指纹、脚本入口和异常条件，不复制完整聊天。执行者不重选文章、不改已确认文本、不绕过403。缓存URL/时间/原始响应，有限并发、超时和重试；已验证PDF断点复用。PDF检查签名、页数、可读性及DOI/题名，拒绝SI/错文。

保留原始HTML/MathML，科学记号无损转换；未知结构升级核实，不按特定DOI硬编码。元数据内容校验通过后一次正式渲染，预览绑定候选哈希。

```text
python scripts/weekly.py --config <本地配置> preflight
python scripts/weekly.py --config <本地配置> prepare-review --records <records.json> --out-dir <新审核目录>
python scripts/weekly.py --config <本地配置> approve --review <review.json> --confirmation "实际用户授权" --output <approved.json>
python scripts/weekly.py --config <本地配置> metadata --approved <approved.json> --journal <所选期刊ID> --evidence <核验补充.json> --output <metadata.json>
python scripts/download_pdfs.py --config <本地配置> --approved <approved.json> --journal <所选期刊ID> --base-dir <配置对应期刊/yyMMdd>
python scripts/update_weekly_docx.py --source <历史Word> --metadata <metadata.json> --date <YYYY.M.D> --output <全新候选.docx>
python scripts/validate_weekly_docx.py --docx <候选.docx> --metadata <metadata.json> --date <YYYY.M.D> --old-docx <历史Word>
python scripts/render_review.py render --config <本地配置> --docx <候选.docx> --output-dir <新渲染目录> --environment-id <渲染器字体环境标识>
python scripts/render_review.py plan --current <render-manifest.json> --force-pages <新增和交界页编号> --output <plan.json>
python scripts/render_review.py accept --config <本地配置> --plan <plan.json> --inspected <真正看过的页编号> --reviewer <实际视觉模型> --output <qa.json>
python scripts/weekly.py --config <本地配置> install --approved <approved.json> --journal <所选期刊ID> --metadata <metadata.json> --candidate <候选.docx> --qa <qa.json>
```

对每个所选期刊同样处理，零新增不运行空块生成。跨期复用须有可信既有QA，同环境且页面像素完全相同；新增/交界/变化页仍实际打开，无法证明一致就检查。accept仅记录真实查看，不代替看图。报告目检X页、复用Y页，不虚报。

默认install在工作区_archive保存验证备份再原子安装，不直接删除旧文件。若项目要求专用归档工具，先按该规则归档并传--archive-receipt（original_path、archived_path、sha256）。失败后若目标已被移走，核对归档后只恢复不存在的目标，不能覆盖其他任务的新文件。

metadata的--evidence只补核实作者/PDF链接和不改变正文的科学标记；不能变更批准的题名、Summary、摘要、日期。费用只用平台实际用量，不推测成已测节省比例。
