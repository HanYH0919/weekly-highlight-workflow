# 来源、去重和文件协议

## 来源与窗口

ACP：<https://acp.copernicus.org/>及其关联ACP的Egusphere预印本。PNAS用官方RSS或日期搜索一种入口；可有记录地因失败切换，分页不算换入口：

- [PNAS RSS](https://www.pnas.org/action/showFeed?ui=0&mi=iqn9jb&type=search&feed=rss&query=%2526access%253Don%2526content%253DarticlesChapters%2526publication%253Dpnas%2526sortBy%253DEarliest%2526target%253Ddefault)
- [PNAS日期搜索](https://www.pnas.org/action/doSearch?field1=AllField&text1=&publication%5B%5D=pnas&publication=&Ppub=&access=on&startPage=0&sortBy=Earliest)

上海时区含首尾10天，起点=执行日期减9。PNAS必须分页覆盖窗口起点或报告覆盖不足；RSS兼容RSS1.0/RDF、DC、PRISM。索引更新时间、Crossref created/deposited/indexed不替代在线发表日期。文章页受限可标记使用出版商Crossref字段或PubMed完整原始摘要；Significance不等于摘要。

## 审核输入

records.json含window `[YYYY-MM-DD, YYYY-MM-DD]`、discovery `{ACP:{source,checked,coverage_complete,stop_reason},PNAS:{...}}`、articles数组。每篇：

```text
journal: ACP或PNAS
type: 正式发表或预印本
doi, title, authors（有序数组）
publication_date: YYYY-MM-DD
date_verified: true；date_source_url
abstract: 完整原始英文摘要
abstract_html: 可选原始HTML/MathML
abstract_verified: true；abstract_source_url；landing_url
screening: {decision: include, question: 主要问题, contribution: 核心增量, relevance: 具体理由}
summary: 待用户审核中文一句话
pdf_url: 可选已核验文章链接，不猜或用SI
```

生成Word前补authors_verified和authors_source_url。布尔标记不是自动查证。缺来源、摘要、日期不得进入已核实清单。

## 去重与审核

prepare-review读取两个实际历史Word及哈希；明确新建的空库可有零历史，损坏/缺失文件不能伪装零历史。本轮、历史DOI先去重；保留合法括号。

related_dois只填已核实版本关系，并有version_relation_verified和version_evidence_url；同轮优先正式版。历史有相关版本则只提示版本更新，不擅自重收或替换。相似题名仅触发version_review_required；查证独立研究可用distinct_from与distinct_evidence_url记录。解决歧义后再正式输出。

去重后写Summary，一般70–110汉字，不凑空话。生成清单先列覆盖与数量，再ACP/PNAS两个代码块，分别编号，Title/裸DOI URL/Summary分行，论文间空行。覆盖不足不能写成“全窗口无符合论文”。

用户按该修订版编号/DOI删改；新增先核验去重。只有明确授权继续才approve，冻结修订和源历史。下载阶段不改变已确认标题、摘要、Summary和顺序。审核前仅可写工作缓存，不下载PDF、不建正式日期目录、不更新Word。

## 文件和安装

目标来自本人本地配置，默认相对结构为Reading/WeeklyHighlight/ACP/ACP.docx及PNAS/PNAS.docx；可在安装时选择实际历史路径。新库只有标题，没有合成论文。首期生成器支持空库；已有文档按原五段模板，未知格式先报告。

正式下载yyMMdd/正式发表、yyMMdd/预印本，来源与状态记录manifest。PDF身份、五段实际内容、作者顺序、科学记号、旧段落格式和独立编号通过后完整渲染。候选验收后先备份归档再原子安装，对比哈希；源变则仅重新去重/构建。没有新条目的期刊不创建空日期块。
