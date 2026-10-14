# 安装 Weekly Highlights 1.11

请本地agent先读SKILL.md。没有默认期刊或主题；收集使用者期刊、领域、数据目录。也可按给定期刊先读官网范围，再按有依据的范围筛选。

## 文件安装

下载v1.11源码或Release ZIP，找到SKILL.md目录，检查脚本后：

    python scripts/install_share.py --platform codex --verify-only
    python scripts/install_share.py --platform codex

可用pi、trae、openclaw；WorkBuddy用ZIP导入或指定已核实的--destination。目标名weekly-highlight-workflow。已有安装先核实版本/优先级，明确升级才加--replace-existing，旧技能会备份，本地路径配置保留。文件导入不等于配置完成。

## 期刊、领域和数据

按 [选择协议](references/selection-setup.md) 生成本人selection.json。selection.example.json是未核实模板，必须填真实选择，不能原样使用。

    python scripts/setup_share.py configure --workspace <本人已有数据根目录> --platform <客户端> --worker-model <实际模型ID> --selection <本人selection.json> --new-library

--new-library为所选各刊创建只有标题的空Word；已有任一目标则拒绝覆盖。沿用已有历史时去掉它，selection填全部实际.docx相对路径，位于根目录内且不重复。支持任意非零期刊数量；未知Word格式先检查。

配置与补充profile在工作根目录.weekly-highlights/。技能目录可写时只保存installation.local.json指针；只读时用--config或WEEKLY_HIGHLIGHTS_CONFIG。优先级为显式参数、环境变量、当前目录祖先配置、安装指针。不要提交本地配置/指针/凭据/测试记录。

需Python3.10+、requirements.txt、LibreOffice及Poppler/pdftoppm；已有工具用--soffice/--pdftoppm配置。doctor检查依赖，脚本不自行装软件。

## 实际视觉测试

    python scripts/vision_probe.py make --config <本地config.json> --output-dir <全新测试目录>

让选定小模型实际打开两张PNG按PROMPT回答，不读answer.private.json、不用OCR或其他模型代答。保存真实模型、回答和图片工具证据：

    python scripts/vision_probe.py grade --challenge <测试目录/challenge.json> --response <response.json> --output <capability.json>
    python scripts/setup_share.py finish --config <本地config.json> --capability <capability.json>

图片输入、模型和全部图像题通过才ready。失败如实记录；经同意回退到另一个实测模型时finish还需--fallback-confirmed和--worker-capability。换模型用models命令并重测，不另索取API密钥。详见 [vision-setup](references/vision-setup.md)。

## 升级或变更范围

1.01配置没有明确研究选择，升级后须显式迁移；以后换刊/领域也用：

    python scripts/setup_share.py scope --config <本地config.json> --selection <本人新selection.json>

新选择缺Word且用户同意新建时加--new-library，仅创建缺失文档，保留所有已有Word。备份配置，不删除移出列表的旧档。范围变化使旧审核/批准包失效，需重新去重审核；模型组合未变时仍验证原真实视觉记录。

就绪后说“帮我做一次Weekly Highlights”，首版清单前已去重，审核同意后再下载和更新Word。

从1.01迁移时，旧的本地筛选profile会先备份，再换为中性模板，避免旧学科偏好残留；原偏好可从备份查阅，但仅将本人仍需要的内容明确加入新research_scope。
