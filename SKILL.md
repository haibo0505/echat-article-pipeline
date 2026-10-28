---
name: wechat-article-pipeline
description: "Create or revise WeChat Official Account articles, plan or generate cover and body images, format Markdown into WeChat-compatible HTML, embed local images, build a portable publishing package, and publish an authorized draft. Use for 公众号文章、公众号排版、配图与完整发布包. Includes its own formatter and themes; no separate xiaohu-wechat-format skill is required."
license: MIT
metadata:
  version: "1.0.0"
---

# 公众号创作、排版与发布

把选题、写作、配图、微信排版和交付连成一个流程。排版引擎、主题、图片嵌入与草稿发布脚本均在本技能内。用户只要排版现成文章时，保留原文事实与意图，不重写整篇。

## 输入与判断

接受主题、笔记、素材、链接或现成 Markdown。只澄清会改变结果的信息；其余采用简体中文、适合手机阅读的短段落和具体标题。标题通常控制在 30 个汉字以内，另给 1–2 个备选。按实际内容组织结构，不为套模板添加虚构案例。

先确定目标读者、场景、核心收益和真实证据。区分事实、估计与观点；缺失信息明确标记。涉及真实作者时提炼高层叙事特征，不冒充本人，不复制原文。

## 完成文章与图片

创建 `article.md`，包含标题、摘要、可扫描的小标题、必要引用与结尾。技术细节只保留读者做决定或执行步骤需要的部分。风险或权限说明只在相关时加入。

使用当前环境可用的图片生成工具生成封面和必要的正文图；也可使用用户提供的图片。工具不可用时交付清晰的图片说明与占位，说明缺少图片，不宣称已经生成。

图片使用 PNG/JPEG，保存在本次项目的 `assets/`。宽幅封面注意缩略图裁切；正文图只在解释流程、证据或结果时添加。保留用户截图中的事实，不修改证据。文字图片逐字校对。

## 运行本技能的完整本地流程

`SKILL_DIR` 指当前读取的本技能目录。脚本路径始终相对此目录解析，不假定用户安装在某个个人账户下。优先使用用户指定的输出位置；Windows 有 D 盘时默认工作和缓存放在 D 盘。

若技能目录内包含 `.venv`，使用其中的 Python（Windows 为 `.venv/Scripts/python.exe`）；否则使用已安装本技能依赖的 Python。

```text
python <SKILL_DIR>/scripts/pipeline.py --input <article.md> --output <新的交付目录> --theme newspaper --cover <assets/cover.png>
```

脚本在交付副本上修复中文标点，排版、复制图片、生成图片内嵌 HTML、检查缺失图片，并生成 ZIP。纯文字排版可省略 `--cover`，但上传草稿必须提供封面。默认拒绝非空输出目录，避免混入上次交付的文件。

主题选择：分析与长文用 `newspaper`，轻量清单用 `magazine`，简洁观点用 `ink`；科技教程可选 `github` 或 `sspai`。更多主题与画廊见 [排版用法](references/formatting.md)。

输出至少包含：

```text
article.md
assets/（引用图片与可选封面）
rendered/article/article.html
rendered/article/preview.html
rendered/article/article-embedded.html
rendered/article/preview-embedded.html
manifest.json
发布说明.md
```

交付目录旁生成 `<目录名>-publish-package.zip`。给用户提供预览、可编辑原稿与 ZIP 的可点击路径，并说明如何复制到微信、在哪里找封面。交付前打开预览检查排版，确认图片都存在、嵌入版不依赖本地图片路径、引用有来源。

## 公众号草稿

只有用户明确要求写入公众号草稿，且已配置本机接口权限时，才执行带 `--publish` 的发布命令。读取 [发布配置](references/publishing.md) 后使用：

```text
python <SKILL_DIR>/scripts/publish.py --dir <交付目录>/rendered/article --cover <封面路径> --publish
```

不带 `--publish` 或带 `--dry-run` 都只进行本地检查，不获取 token、不上传图片、不写草稿。检查命令不需要 AppSecret。真实写入草稿还需要本机凭据和公众号后台 IP 白名单；不要在聊天中索要或回显密钥。

脚本仅支持写入草稿，没有群发功能。用户只要求生成文章或发布包时，在本地交付结束，不调用公众号接口。发布失败时保留包和明确的错误原因，不无限重试或自动更换账户。

## 配置与限制

纯排版无需创建 `config.json`，安装 Python 依赖后即可使用。可选配置、环境变量、Windows 路径和 SVG 处理见 [排版用法](references/formatting.md)。内置排版为本地功能，不要求外部大模型 API；图片生成工具如有费用，遵守当前用户的授权范围。

发布包不包含本机配置、凭据、聊天记录或绝对个人路径。仅导出当前文章引用的素材。上游来源、固定版本及修改说明见 [NOTICE.md](NOTICE.md)。
