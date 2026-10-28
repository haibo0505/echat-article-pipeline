# 公众号创作、排版与发布 · WeChat Article Pipeline

一个完整的 Agent Skill：选题与写作 → 配图 → 微信排版 → 图片内嵌 → ZIP 发布包 → 获得授权后写入公众号草稿。

合并了 `wechat-article-pipeline` 的文章工作流和 [xiaohuailabs/xiaohu-wechat-format](https://github.com/xiaohuailabs/xiaohu-wechat-format) 的排版引擎，**无需再安装第二个排版技能**。支持 Codex，也可在支持 `SKILL.md` 的其他助手中使用；本地工具支持 Windows、macOS 和 Linux。

## 功能

- 在助手中完成选题、文章撰写和图片生成规划；图片生成使用当前助手可用的工具。
- 内置 85 套主题，支持中文标点处理、内联样式、引用、列表、表格、对话与精选主题画廊。
- 生成普通及图片内嵌的文章 HTML、预览页面、素材、校验清单和便携 ZIP。
- 原始文章保持不变，只在交付副本上修正标点；只打包引用素材。
- Windows 中文路径、带空格文件名、同名图片及标准文件 URI 处理。
- **默认与 `--dry-run` 均零微信网络请求**；只有显式 `--publish` 才上传图片、创建草稿。

## 安装为技能

Python 3.10+。将仓库放入技能目录，或从用户技能目录创建指向仓库的目录链接。下面是 Windows D 盘示例：

```powershell
git clone https://github.com/haibo0505/echat-article-pipeline.git D:\APP\wechat-article-pipeline
python -m venv D:\APP\wechat-article-pipeline\.venv
D:\APP\wechat-article-pipeline\.venv\Scripts\python.exe -m pip install -r D:\APP\wechat-article-pipeline\requirements.txt
```

在你的助手支持的用户技能目录中创建 `wechat-article-pipeline` 链接，目标指向上述 D 盘目录。**已有同名技能时先备份，勿覆盖链接指向的现有内容。**也可以让 Codex 的技能安装器从本仓库安装。

在 Codex 下一轮输入：

```text
$wechat-article-pipeline 根据我的素材写一篇公众号文章，生成配图并交付完整发布包。
```

助手读取 [SKILL.md](SKILL.md)，脚本和主题均在本技能内。图片工具或公众号接口不可用时，会说明缺少的部分，不宣称已完成远程操作。

## 仅使用命令行

本地排版不需要公众号密钥或外部大模型 API：

```text
python -m pip install -r requirements.txt
python scripts/pipeline.py --input examples/article.md --output delivery --theme newspaper
```

添加本地封面和图片后，可用：

```text
python scripts/pipeline.py --input article.md --output delivery-with-images --theme newspaper --cover assets/cover.png
```

得到：

```text
delivery/
  article.md
  assets/                    # 有引用图片时生成
  rendered/article/
    article.html
    preview.html
    article-embedded.html
    preview-embedded.html
    images/                  # 有引用图片时生成
  manifest.json
  发布说明.md
delivery-publish-package.zip
```

输出目录必须为空。`manifest.json` 记录相对文件路径、大小与 SHA-256；包中不包含本机配置和凭据。

## 主题与画廊

```text
python scripts/format.py --input examples/article.md --gallery --output gallery --no-open
```

打开 `gallery/article/gallery.html` 预览并复制所选主题名，然后使用该主题重新生成发布包。默认不自动打开浏览器。完整说明见 [references/formatting.md](references/formatting.md)。

## 检查与写入草稿

先做本地检查，不需要微信凭据：

```text
python scripts/publish.py --dir delivery-with-images/rendered/article --cover assets/cover.png --dry-run
```

准备好已有公众号接口权限、IP 白名单及本机配置后，明确要求写入草稿：

```text
python scripts/publish.py --dir delivery-with-images/rendered/article --cover assets/cover.png --publish
```

推荐通过 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_AUTHOR` 配置。也可使用不进入 Git 的私有 `config.json`。**不要把实际密钥填入公开样例、提交或聊天。**脚本不提供群发接口。具体行为和失败处理见 [references/publishing.md](references/publishing.md)。

## 路径与配置

`--output` 决定本次交付位置。`WECHAT_PIPELINE_HOME` 决定默认数据与缓存根目录；Windows 检测到 D 盘时默认放在 `D:/APP/wechat-article-pipeline-data`，其他环境放在当前目录的 `wechat-output`。配置读取不创建文件。

纯排版无需 `config.json`；可选配置参见 [config.example.json](config.example.json)。支持 `WECHAT_PIPELINE_CONFIG` 指向独立的私有配置文件。

## 验证与限制

```text
python -m unittest discover -s tests -v
```

测试覆盖完整发布包、全部 85 套主题的 HTML 生成、画廊缓存、中文路径、图片嵌入、同名图片、零网络预检查和离线草稿流程。真实公众号发布需在自己的账号配置后验证；本项目测试不连接公众号。微信后台粘贴及手机显示仍需人工预览。

正文图片打包前需保存到本地；SVG 请先转 PNG/JPEG。图片生成依赖助手可用工具，外部模型增强仅在用户显式要求并配置接口时使用。

## 来源与许可

MIT。感谢 [xiaohuailabs/xiaohu-wechat-format](https://github.com/xiaohuailabs/xiaohu-wechat-format) 的排版引擎、主题与模板。固定来源和修改范围见 [NOTICE.md](NOTICE.md)，许可见 [LICENSE](LICENSE)。
