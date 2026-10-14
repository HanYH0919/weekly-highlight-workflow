# 自选期刊与研究范围

用户可给期刊及研究领域，也可只给期刊并授权agent阅读后找相关内容，或明确要求期刊全领域。没有作者默认期刊、学科或关联预印本。

只给期刊时联网核实全名、官网、ISSN（有则记录），阅读官方Aims & Scope和近期文章，说明采用范围并保存依据。授权按期刊范围时用journal-informed。不能把综合刊少数文章推断为个人领域；“相关”指向不明且影响结果时询问，已授权期刊完整范围时继续。all只在明确授权时使用。

本地selection.json有三字段，与config中的同名字段相同：

- journals：期刊ID到Word相对路径的非空映射；如J1到Reading/WeeklyHighlight/J1/J1.docx。ID为1–64位字母/数字/连字符/下划线，全名可任意语言放在profile.name。每刊路径不同，均在数据根目录内。
- journal_profiles：同一组ID。每刊含name、source_urls（实际核实的官方入口数组）、source_verified:true；可加ISSN等身份信息。include_preprints默认false，true须有preprint_source_urls且核实与所选范围关系。不能只按DOI前缀猜期刊。
- research_scope：mode为topics、journal-informed、all；topics/exclude为字符串数组（exclude可空）；criteria为具体筛选标准。topics模式须非空topics；journal-informed须已读官方范围/文章的evidence_urls。可在criteria中给每刊不同侧重点。

selection.example.json故意处于未配置状态，需由agent填使用者真实选择并核实。source_verified只是检查记录，脚本不能代替判断期刊真伪。

record.journal、discovery键和--journal均用配置期刊ID。discovery包括零新增期刊；不允许额外或遗漏。预印本不自动扩展到别的平台或学科。

scope命令备份原配置，只更新选择及版本；保留模型、视觉设置、原Word和移出列表的旧档。新增缺失文档需显式--new-library。1.01升级不能悄悄保留旧作者专业偏好。

review/approved冻结选择指纹；期刊、路径、来源、领域或排除项变化后，旧包不能approve/metadata/download/install。补充profile会影响选文时也要同步至research_scope.criteria再生成清单。

从1.01迁移时，旧的本地筛选profile会先备份，再换为中性模板，避免旧学科偏好残留；原偏好可从备份查阅，但仅将本人仍需要的内容明确加入新research_scope。
