# 来源、去重和文件协议

目标来自本地journals/journal_profiles，没有默认期刊或学科。核实各刊身份与官网，使用官方目录/RSS/日期搜索等入口分页覆盖窗口，失败有记录地切换。预印本仅纳入显式来源。

默认上海时区含首尾10天；timezone/window_days可配置。通用RSS/RDF/Atom及citation文章元数据解析、显式article-xpath/title-xpath/link-xpath目录选择器、浏览器辅助均可。脚本结果只是候选，默认日期/摘要未核实。不能将解析失败当空刊。

以在线发表/预印本原始日期为准，不用索引更新时间或Crossref created/deposited/indexed代替。完整摘要附来源，不将题名/Significance当摘要，不虚构英文翻译作为原文。

records.json包含window [YYYY-MM-DD,YYYY-MM-DD]，discovery为每个选中期刊ID对应的{source,checked,coverage_complete,stop_reason}，articles数组。discovery须与配置完全相同，包括零新增刊。每篇：
- journal：选中ID；type：正式发表或预印本
- doi,title,authors（有序数组）,publication_date
- date_verified:true,date_source_url
- abstract（完整原始摘要）,abstract_html（可选原始HTML/MathML）
- abstract_verified:true,abstract_source_url,landing_url
- screening:{decision:include,question,contribution,relevance}
- summary：待审核中文一句话；pdf_url：可选已核实文章PDF

生成Word前补authors_verified、authors_source_url。布尔标记只是记录真实核验，不是脚本自动保证；核实文章属于目标期刊，不按DOI前缀猜。

读取全部选中历史Word及指纹。显式新库可以零历史；缺失/损坏不能伪装空库。跨所选期刊统一做本轮/历史DOI去重；合法括号保留。related_dois须有version_relation_verified和version_evidence_url，同轮优先正式版；历史已有相关版本只报告更新，不擅自重复收录。

相似题名仅触发version_review_required，独立研究用distinct_from和distinct_evidence_url证明。歧义解决前输出阻断审计，不输出正式清单。

每刊独立编号与复制块，数量随选择变化，Title/裸DOI URL/Summary分行。先报范围、覆盖、重复和入选数；覆盖不足不写全窗口无符合论文。Summary一般70–110汉字，尊重用户要求。

用户审核后approve冻结选择指纹、修订和历史；范围变化须重做。新增先核验去重，审核前不下载PDF、不建正式日期目录、不改Word。

各刊Word路径来自配置，新库只有标题。首期支持空库，既有Word用原五段模板，未知格式先检查。下载在对应Word父目录/yyMMdd/正式发表或预印本，记录manifest。零新增不建空块。PDF身份、内容、作者、科学记号、旧格式与编号验证后完整渲染实际看图，验证备份后原子安装并比哈希。
