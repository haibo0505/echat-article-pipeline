"""Build a self-contained WeChat article package without network access."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlparse
import zipfile

from _config import configure_console, load_config
from embed_images import embed_html
from zh_punctuation_fix import fix

SCRIPT_DIR = Path(__file__).resolve().parent
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
WIKI_IMAGE = re.compile(r"!\[\[([^\]]+)\]\]")


class ImageCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            self.sources.extend(value for name, value in attrs if name.lower() == "src" and value)


def image_sources(html: str) -> list[str]:
    parser = ImageCollector()
    parser.feed(html)
    return parser.sources


def prepare_article(input_path: Path, output: Path, theme: str = "newspaper", cover: Path | None = None) -> dict:
    input_path = input_path.expanduser().resolve()
    output = output.expanduser().resolve()
    archive = output.with_name(output.name + "-publish-package.zip")
    if not input_path.is_file():
        raise ValueError("找不到输入文章")
    if output.exists() and any(output.iterdir()):
        raise ValueError("输出目录非空，请选择新的交付目录")
    if archive.exists():
        raise ValueError("发布包已存在，请选择新的交付目录名称")
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"

    def stage_image(path: Path) -> Path:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise ValueError("缺少文章引用的图片：" + path.name)
        if path.suffix.lower() == ".svg":
            raise ValueError("SVG 请先转成 PNG/JPEG：" + path.name)
        data = path.read_bytes()
        suffix = hashlib.sha256(data).hexdigest()[:12]
        stem = re.sub(r"[^\w.-]+", "-", path.stem, flags=re.U)[:80] or "image"
        assets.mkdir(exist_ok=True)
        destination = assets / f"{stem}-{suffix}{path.suffix.lower()}"
        if not destination.exists():
            destination.write_bytes(data)
        return destination

    content = input_path.read_text(encoding="utf-8-sig")

    def replace_markdown_image(match):
        source = match.group(2).strip()
        if source.startswith(("http://", "https://", "data:", "//")):
            raise ValueError("请先把正文图片保存到本地 assets 目录，再生成便携发布包")
        path = (input_path.parent / unquote(source)).resolve()
        staged = stage_image(path)
        return f"![{match.group(1)}]({staged.relative_to(output).as_posix()})"

    def replace_wiki_image(match):
        source = match.group(1).split("|", 1)[0].strip()
        candidate = input_path.parent / source
        if not candidate.is_file():
            matches = list(input_path.parent.rglob(source)) if "/" not in source and "\\" not in source else []
            if len(matches) != 1:
                raise ValueError("无法唯一定位 Obsidian 图片：" + source)
            candidate = matches[0]
        staged = stage_image(candidate)
        return f"![{Path(source).stem}]({staged.relative_to(output).as_posix()})"

    # Do not treat images inside fenced code blocks or inline code as dependencies.
    protected = []
    def protect_code(match):
        protected.append(match.group(0))
        return f"\x00CODE{len(protected) - 1}\x00"
    content = re.sub(r"```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`", protect_code, content)
    content = WIKI_IMAGE.sub(replace_wiki_image, content)
    content = MD_IMAGE.sub(replace_markdown_image, content)
    for index, value in enumerate(protected):
        content = content.replace(f"\x00CODE{index}\x00", value)
    staged_cover = stage_image(cover) if cover else None
    article = output / "article.md"
    article.write_text(fix(content), encoding="utf-8")
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, str(SCRIPT_DIR / "format.py"), "--input", str(article), "--output", str(output / "rendered"),
               "--vault-root", str(output), "--theme", theme, "--no-open"]
    result = subprocess.run(command, cwd=output, env=environment, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise ValueError("本地排版失败：" + (result.stderr.strip() or result.stdout.strip()))
    rendered = output / "rendered/article"
    for name in ("article.html", "preview.html"):
        source = rendered / name
        for src in image_sources(source.read_text(encoding="utf-8")):
            if urlparse(src).scheme or src.startswith("//") or not (rendered / unquote(src)).is_file():
                raise ValueError("排版结果存在未解决的图片引用")
        destination = rendered / (source.stem + "-embedded.html")
        embed_html(source, destination)
        if any(not src.startswith("data:image/") for src in image_sources(destination.read_text(encoding="utf-8"))):
            raise ValueError("图片嵌入不完整")
    cover_note = staged_cover.relative_to(output).as_posix() if staged_cover else "本次未提供；写入公众号草稿前需要封面"
    notes = f"""# 发布说明

1. 打开 `rendered/article/preview-embedded.html`，检查标题、图片与手机阅读效果。
2. 点击“复制到微信”，粘贴到公众号图文编辑器；若浏览器限制剪贴板，手动选中正文复制。
3. 封面：`{cover_note}`。
4. 需要修改文字时编辑 `article.md`，再用新的输出目录生成一份发布包。
5. 内嵌图片过大时，使用普通 `preview.html` 并在微信后台上传 `assets/` 或 `rendered/article/images/` 中的图片。
6. 发布包没有公众号凭据；需要自动写入草稿时，在本机配置后明确执行 `publish.py --publish`。

本次只完成本地准备，没有上传图片或写入公众号草稿。
"""
    (output / "发布说明.md").write_text(notes, encoding="utf-8")
    files = {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(output.rglob("*")) if path.is_file()}
    manifest = {"schema_version": 1, "theme": theme, "cover": staged_cover.relative_to(output).as_posix() if staged_cover else None,
                "files": files, "network_used": False}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                package.write(path, arcname=output.name + "/" + path.relative_to(output).as_posix())
    return {"output": str(output), "preview": str(rendered / "preview-embedded.html"), "article_dir": str(rendered),
            "cover": str(staged_cover) if staged_cover else None, "zip": str(archive), "files": len(files) + 1}


def main():
    parser = argparse.ArgumentParser(description="公众号文章排版、图片嵌入与发布包生成（全程本地）")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="新的交付目录；不覆盖非空目录")
    parser.add_argument("--theme", default=load_config()["settings"]["default_theme"])
    parser.add_argument("--cover", type=Path)
    args = parser.parse_args()
    destination = args.output or (Path(load_config()["output_dir"]) / args.input.stem)
    try:
        result = prepare_article(args.input, destination, args.theme, args.cover)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    configure_console()
    main()
