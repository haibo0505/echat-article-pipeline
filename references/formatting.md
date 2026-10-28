# 排版、主题与本地配置

## Python 与安装目录

需要 Python 3.10 或更新版本。已安装技能若带 `.venv`，优先使用技能目录内 `.venv/Scripts/python.exe`（Windows）或 `.venv/bin/python`（macOS/Linux）；否则使用已安装本项目依赖的 Python。

```text
python -m pip install -r <SKILL_DIR>/requirements.txt
```

纯排版不需要微信凭据，也不需要创建 `config.json`。运行脚本前确认使用正确的 Python，缺少依赖时按当前环境的安装权限处理。

## 完整发布包

```text
python <SKILL_DIR>/scripts/pipeline.py --input article.md --output delivery --theme newspaper --cover assets/cover.png
```

`--output` 是新建交付目录；非空目录会被保留并报错。原始文章和图片不会被修改。图片的相对路径以原稿所在目录为基准，封面参数以当前工作目录为基准。只复制实际引用的图片，不复制原稿目录中的其他文件。

支持标准 Markdown 图片、Obsidian 图片引用，以及名称含空格或中文的本地图片。正文中的代码示例不会被当作图片依赖。为了让 ZIP 可携带，正文远程图片要先保存到本地；包内的链接仍可指向外部参考资料。

图片优先用 PNG/JPEG。SVG 会明确报错，不调用 macOS 专属工具、不悄悄输出微信无法接收的文件；先用合适的图像工具转换后再运行。WebP 在实际上传前可转换为 PNG，但本地配图优先直接使用 PNG/JPEG。

## 指定主题或打开画廊

项目包含上游固定版本的 85 套主题。常用选项：

| 文章 | 主题 |
| --- | --- |
| 分析、深度长文 | `newspaper`、`magazine`、`ink` |
| 科技产品、教程 | `github`、`sspai`、`bytedance` |
| 访谈、对话 | `interview`、`terracotta` |
| 数据简报 | `data-report` |

仅格式化一个文件：

```text
python <SKILL_DIR>/scripts/format.py --input article.md --theme newspaper --output rendered --no-open
```

浏览精选主题：

```text
python <SKILL_DIR>/scripts/format.py --input article.md --gallery --output gallery --no-open
```

生成后打开 `gallery/<原稿文件名>/gallery.html`。用户切换主题、字号后，将选择复制回对话，再用对应主题重新生成完整发布包。静态画廊不把浏览器中的最终选择自动写回 Python 进程。

默认不自动启动浏览器。可在本机配置的 `settings.auto_open_browser` 设为 `true`；Windows 文件链接通过标准文件 URI 打开。

## 可选配置

复制 `config.example.json` 为本机 `config.json`，只填写需要覆盖的项；空路径使用默认值。配置文件在版本控制和技能分发包中排除。`WECHAT_PIPELINE_CONFIG` 可以指向别处的私有配置文件。

`WECHAT_PIPELINE_HOME` 设置默认数据根目录。未设置时，Windows 有 D 盘就用 `D:/APP/wechat-article-pipeline-data`；其他环境用当前目录下的 `wechat-output`。配置中的相对路径以配置文件目录为基准，命令行路径以当前工作目录为基准。

支持配置 `output_dir`、`vault_root`、`cache_dir`、`image_search_paths` 和默认主题。环境变量和 CLI 输出位置应遵守当前用户的存储约定。画廊状态和发布临时图片都使用配置的缓存目录。

排版引擎保留上游可选的 `--smart` 语义增强入口；该选项可能调用外部大模型 API，需要用户明确要求、配置接口并允许相应费用。常规完整工作流不调用此入口，由当前助手完成写作和结构判断。
