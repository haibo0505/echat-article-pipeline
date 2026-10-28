"""Validate locally by default; --publish explicitly uploads a WeChat draft."""

from __future__ import annotations

import argparse
from html import unescape
import json
import mimetypes
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlparse

from _config import cache_dir, configure_console, load_config
from pipeline import image_sources, prepare_article

API = "https://api.weixin.qq.com/cgi-bin"


def credential_fields(config: dict) -> tuple[str, str]:
    wechat = config.get("wechat", {})
    values = (str(wechat.get("app_id", "")).strip(), str(wechat.get("app_secret", "")).strip())
    if any(not value or value.upper().startswith("YOUR_") for value in values):
        raise ValueError("真实发布需要在本机配置 WECHAT_APP_ID 和 WECHAT_APP_SECRET，或私有 config.json")
    return values


def title_from_html(text: str) -> str:
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", text, re.I | re.S)
    return unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""


def inspect_article(article_dir: Path, cover: Path | None, title: str | None = None) -> dict:
    article_dir = article_dir.expanduser().resolve()
    article = article_dir / "article.html"
    if not article.is_file():
        raise ValueError("目录中缺少 article.html")
    text = article.read_text(encoding="utf-8")
    resolved_title = title or title_from_html(text)
    if not resolved_title:
        raise ValueError("文章没有标题，请提供 --title")
    if len(resolved_title) > 64:
        raise ValueError("标题超过 64 个字符，请缩短后再发布")
    if cover:
        cover = cover.expanduser()
        cover = cover.resolve() if cover.is_absolute() else (article_dir / cover).resolve()
    else:
        cover = next(iter(sorted((article_dir / "images").glob("cover*"))), None)
    if not cover or not cover.is_file():
        raise ValueError("草稿需要封面，请用 --cover 指定本地 PNG/JPEG 图片")
    with cover.open("rb") as stream:
        if not stream.read(1):
            raise ValueError("封面图片为空")
    sources = list(dict.fromkeys(image_sources(text)))
    local, remote = [], []
    for src in sources:
        parsed = urlparse(src)
        if parsed.scheme in ("http", "https"):
            remote.append(src)
        elif parsed.scheme or src.startswith("//"):
            raise ValueError("发布请使用普通 article.html 和本地图片，不使用 data URI 或 file URL")
        else:
            image = (article_dir / unquote(src)).resolve()
            if not image.is_file():
                raise ValueError("缺少正文图片：" + Path(unquote(src)).name)
            local.append(image)
    return {"article_dir": article_dir, "article": article, "html": text, "title": resolved_title,
            "cover": cover, "sources": sources, "local_images": local, "remote_images": remote}


class WeChatClient:
    def __init__(self, config: dict):
        app_id, app_secret = credential_fields(config)
        import requests
        self.session = requests.Session()
        self._requests = requests
        data = self._request("get", API + "/token", params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret}).json()
        self._check(data)
        self.token = data.get("access_token")
        if not self.token:
            raise ValueError("微信未返回 access_token")

    def _request(self, method: str, url: str, **kwargs):
        try:
            response = getattr(self.session, method)(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except self._requests.RequestException:
            # Requests exceptions can include credential-bearing URLs; keep them local.
            raise ValueError("微信或图片接口请求失败，请检查网络、接口权限与 IP 白名单") from None

    @staticmethod
    def _check(data: dict):
        if data.get("errcode", 0):
            raise ValueError("微信接口错误码：" + str(data["errcode"]))

    def upload(self, image: Path, *, cover: bool = False) -> str:
        endpoint = "/material/add_material" if cover else "/media/uploadimg"
        params = {"access_token": self.token}
        if cover:
            params["type"] = "image"
        with image.open("rb") as stream:
            data = self._request("post", API + endpoint, params=params,
                                 files={"media": (image.name, stream, mimetypes.guess_type(image.name)[0] or "image/png")}).json()
        self._check(data)
        value = data.get("media_id" if cover else "url")
        if not value:
            raise ValueError("微信图片接口未返回图片标识")
        return value

    def download(self, url: str) -> bytes:
        return self._request("get", url).content

    def draft(self, title: str, text: str, thumb: str, author: str, source_url: str) -> str:
        payload = {"articles": [{"title": title, "author": author, "content": text, "thumb_media_id": thumb,
                                 "content_source_url": source_url, "need_open_comment": 0, "only_fans_can_comment": 0}]}
        data = self._request("post", API + "/draft/add", params={"access_token": self.token},
                             data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                             headers={"Content-Type": "application/json"}).json()
        self._check(data)
        if not data.get("media_id"):
            raise ValueError("微信未返回草稿标识")
        return data["media_id"]


def normalized_image(path: Path, destination: Path) -> Path:
    from PIL import Image
    try:
        with Image.open(path) as image:
            if image.format in ("PNG", "JPEG", "GIF"):
                allowed = {"PNG": (".png",), "JPEG": (".jpg", ".jpeg"), "GIF": (".gif",)}[image.format]
                if path.suffix.lower() in allowed:
                    return path
                renamed = destination.with_suffix(allowed[0])
                renamed.write_bytes(path.read_bytes())
                return renamed
            converted = destination.with_suffix(".png")
            image.convert("RGBA").save(converted, format="PNG")
            return converted
    except (OSError, ValueError):
        raise ValueError("无法读取图片，请使用有效的 PNG/JPEG/GIF：" + path.name) from None


def publish_article(article: dict, config: dict, author: str = "", source_url: str = "", *, client_factory=None) -> dict:
    # All local validation precedes client construction and the first network request.
    credential_fields(config)
    from PIL import Image
    for image in [article["cover"], *article["local_images"]]:
        try:
            with Image.open(image) as opened:
                opened.verify()
        except (OSError, ValueError):
            raise ValueError("发布前图片检查失败：" + image.name) from None
    temporary_root = cache_dir(config).resolve()
    temporary_root.mkdir(parents=True, exist_ok=True)
    client = (client_factory or WeChatClient)(config)
    with tempfile.TemporaryDirectory(prefix="publish-", dir=temporary_root) as temporary:
        temporary = Path(temporary).resolve()
        if not temporary.is_relative_to(temporary_root):
            raise ValueError("临时目录不在指定缓存目录内")
        replacements = {}
        for index, src in enumerate(article["sources"]):
            if src.startswith(("http://", "https://")):
                if urlparse(src).hostname == "mmbiz.qpic.cn":
                    replacements[src] = src
                    continue
                local = temporary / f"download-{index}.image"
                local.write_bytes(client.download(src))
            else:
                local = (article["article_dir"] / unquote(src)).resolve()
            image = normalized_image(local, temporary / f"body-{index}.png")
            replacements[src] = client.upload(image)
        cover = normalized_image(article["cover"], temporary / "cover.png")
        thumb = client.upload(cover, cover=True)
        def replace(match):
            key = unescape(match.group(2))
            return "src=" + match.group(1) + replacements.get(key, key) + match.group(1)
        text = re.sub(r"\bsrc\s*=\s*([\"\x27])(.*?)\1", replace, article["html"], flags=re.I)
        media_id = client.draft(article["title"], text, thumb, author or config.get("wechat", {}).get("author", ""), source_url)
    result = {"status": "draft_created", "media_id": media_id, "title": article["title"]}
    (article["article_dir"] / "publish-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="公众号本地发布检查；显式 --publish 才上传图片和创建草稿")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dir", type=Path)
    group.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, help="--input 模式的新交付目录")
    parser.add_argument("--cover", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--theme", default="newspaper")
    parser.add_argument("--author", default="")
    parser.add_argument("--source-url", default="")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只做本地检查，零微信接口请求")
    mode.add_argument("--publish", action="store_true", help="上传图片并创建公众号草稿")
    args = parser.parse_args(argv)
    try:
        config = load_config()
        cover = args.cover
        if args.input:
            output = args.output or Path(config["output_dir"]) / args.input.stem
            prepared = prepare_article(args.input, output, args.theme, cover)
            article_dir = Path(prepared["article_dir"])
            cover = Path(prepared["cover"]) if prepared["cover"] else None
        else:
            article_dir = args.dir
            if cover:
                cover = cover.expanduser().resolve()
        article = inspect_article(article_dir, cover, args.title)
        if not args.publish:
            try:
                credential_fields(config)
                credentials_ready = True
            except ValueError:
                credentials_ready = False
            result = {"status": "local_check_passed", "title": article["title"], "local_images": len(article["local_images"]),
                      "remote_images": len(article["remote_images"]), "credentials_configured": credentials_ready,
                      "network_requests": 0, "draft_created": False}
        else:
            result = publish_article(article, config, args.author, args.source_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    configure_console()
    raise SystemExit(main())
