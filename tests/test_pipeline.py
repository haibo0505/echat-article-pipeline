"""Offline integration and publishing-boundary tests. No live credentials required."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from PIL import Image
import _config
import pipeline
import publish


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="wechat-skill-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = cls.base / "中文 原始素材"
        (cls.source / "assets").mkdir(parents=True)
        cls.cover = cls.source / "assets/cover.png"
        cls.picture = cls.source / "assets/正文 图片.png"
        Image.new("RGB", (32, 16), "navy").save(cls.cover)
        Image.new("RGB", (16, 32), "orange").save(cls.picture)
        cls.article = cls.source / "中文 文章.md"
        cls.source_text = "# 公众号完整流程测试\n\n## 方法\n\n中文标点,需要修复:这是测试!\n\n![正文图](assets/正文 图片.png)\n\n[资料](https://example.org/info)\n\n- 第一项\n- 第二项\n\n```markdown\n![示例](missing-example.png)\n```\n"
        cls.article.write_text(cls.source_text, encoding="utf-8")
        (cls.source / ".env").write_text("DO_NOT_EXPORT=private-fixture", encoding="utf-8")
        (cls.source / "config.json").write_text('{"private_fixture": true}', encoding="utf-8")
        cls.env_patch = mock.patch.dict(os.environ, {"WECHAT_PIPELINE_HOME": str(cls.base / "data"),
                                                    "WECHAT_PIPELINE_CONFIG": str(cls.base / "absent-config.json"),
                                                    "WECHAT_APP_ID": "", "WECHAT_APP_SECRET": "", "PYTHONUTF8": "1",
                                                    "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        cls.env_patch.start()
        cls.package = pipeline.prepare_article(cls.article, cls.base / "完整交付", "newspaper", cls.cover)

    @classmethod
    def tearDownClass(cls):
        cls.env_patch.stop()
        if not cls.base.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise AssertionError("Test cleanup is outside the temporary workspace")
        cls.temporary.cleanup()

    def test_complete_package_and_source_preservation(self):
        output = Path(self.package["output"])
        self.assertEqual(self.article.read_text(encoding="utf-8"), self.source_text)
        self.assertIn("中文标点，需要修复：这是测试！", (output / "article.md").read_text(encoding="utf-8"))
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["network_used"])
        for name in ("article-embedded.html", "preview-embedded.html"):
            sources = pipeline.image_sources((output / "rendered/article" / name).read_text(encoding="utf-8"))
            self.assertTrue(sources)
            self.assertTrue(all(src.startswith("data:image/png;base64,") for src in sources))
        with zipfile.ZipFile(self.package["zip"]) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.endswith("manifest.json") for name in names))
            self.assertFalse(any(name.endswith((".env", "config.json")) for name in names))
            self.assertNotIn(b"private-fixture", b"".join(archive.read(name) for name in names))
        self.assertNotIn(str(self.source), (output / "manifest.json").read_text(encoding="utf-8"))

    def test_required_themes_and_all_theme_files_render(self):
        specification = importlib.util.spec_from_file_location("skill_formatter", ROOT / "scripts/format.py")
        formatter = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(formatter)
        themes = sorted((ROOT / "themes").glob("*.json"))
        self.assertEqual(len(themes), 85)
        for path in themes:
            with self.subTest(theme=path.stem):
                theme = formatter.load_theme(path.stem)
                rendered = formatter.format_for_output("# 测试标题\n\n正文。\n\n## 小节\n\n- 清单", self.article, theme,
                                                       self.base / "theme-output" / path.stem, self.source)
                self.assertIn("正文", rendered["html"])
                self.assertIn('style="', rendered["html"])
        for theme in ("magazine", "ink"):
            result = pipeline.prepare_article(self.article, self.base / ("package-" + theme), theme, self.cover)
            self.assertTrue(Path(result["preview"]).is_file())

    def test_gallery_uses_configured_cache(self):
        output = self.base / "gallery"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/format.py"), "--input", str(self.article),
                                 "--output", str(output), "--gallery", "--no-open"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((output / self.article.stem / "gallery.html").is_file())
        self.assertTrue((self.base / "data/cache/selected-theme.txt").is_file())

    def test_duplicate_image_basenames_preserve_both_images(self):
        source = self.base / "collision-source"
        for directory, color in (("a", "red"), ("b", "blue")):
            (source / directory).mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), color).save(source / directory / "same.png")
        article = source / "article.md"
        article.write_text("# 两张图片\n\n![a](a/same.png)\n\n![b](b/same.png)", encoding="utf-8")
        result = pipeline.prepare_article(article, self.base / "collision-package")
        folder = Path(result["article_dir"])
        sources = pipeline.image_sources((folder / "article.html").read_text(encoding="utf-8"))
        self.assertEqual(len(set(sources)), 2)
        self.assertNotEqual((folder / unquote(sources[0])).read_bytes(), (folder / unquote(sources[1])).read_bytes())

    def test_default_and_dry_run_do_not_construct_network_client(self):
        for flags in ([], ["--dry-run"]):
            with self.subTest(flags=flags), mock.patch.object(publish, "WeChatClient", side_effect=AssertionError("network client used")), \
                 mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network used")), contextlib.redirect_stdout(io.StringIO()) as output:
                result = publish.main(["--dir", self.package["article_dir"], "--cover", self.package["cover"], *flags])
                self.assertEqual(result, 0)
                data = json.loads(output.getvalue())
                self.assertEqual(data["network_requests"], 0)
                self.assertFalse(data["draft_created"])
                self.assertFalse(data["credentials_configured"])

    def test_missing_image_stops_before_publish(self):
        folder = self.base / "missing-image"
        folder.mkdir()
        (folder / "article.html").write_text('<h1>缺图测试</h1><img src="missing.png">', encoding="utf-8")
        with mock.patch.object(publish, "WeChatClient", side_effect=AssertionError("network client used")):
            with self.assertRaisesRegex(ValueError, "缺少正文图片"):
                publish.inspect_article(folder, self.cover)

    def test_explicit_publish_sequence_with_offline_client(self):
        inspected = publish.inspect_article(Path(self.package["article_dir"]), Path(self.package["cover"]))
        calls = []
        class OfflineClient:
            def __init__(self, config): calls.append("token")
            def upload(self, path, *, cover=False):
                calls.append("cover" if cover else "body")
                return "offline-cover" if cover else "https://mmbiz.qpic.cn/offline-body"
            def draft(self, title, text, thumb, author, source_url):
                calls.append("draft")
                self.assertion = "https://mmbiz.qpic.cn/offline-body" in text
                if not self.assertion: raise AssertionError("CDN image not inserted")
                return "offline-draft-id"
        config = _config.load_config()
        config["wechat"].update(app_id="offline-fixture", app_secret="offline-placeholder")
        result = publish.publish_article(inspected, config, client_factory=OfflineClient)
        self.assertEqual(calls, ["token", "body", "cover", "draft"])
        self.assertEqual(result["status"], "draft_created")
        self.assertNotIn("offline-placeholder", json.dumps(result))

    def test_missing_credentials_fail_before_network(self):
        inspected = publish.inspect_article(Path(self.package["article_dir"]), Path(self.package["cover"]))
        with mock.patch.object(publish, "WeChatClient", side_effect=AssertionError("network client used")):
            with self.assertRaisesRegex(ValueError, "本机配置"):
                publish.publish_article(inspected, _config.load_config())

    def test_nonempty_output_is_preserved(self):
        output = self.base / "preserved"
        output.mkdir()
        sentinel = output / "existing.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "输出目录非空"):
            pipeline.prepare_article(self.article, output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")

    def test_browser_preview_uses_valid_file_uri(self):
        specification = importlib.util.spec_from_file_location("uri_formatter", ROOT / "scripts/format.py")
        formatter = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(formatter)
        arguments = ["format.py", "--input", str(self.article), "--output", str(self.base / "浏览器 输出"), "--theme", "newspaper"]
        with mock.patch.object(formatter, "AUTO_OPEN", True), mock.patch.object(sys, "argv", arguments), \
             mock.patch.object(formatter.webbrowser, "open") as opened, contextlib.redirect_stdout(io.StringIO()):
            formatter.main()
        uri = opened.call_args.args[0]
        self.assertTrue(uri.startswith("file:///"))
        self.assertNotIn("\\", uri)
        self.assertIn("%20", uri)

    def test_image_normalization_converts_webp(self):
        image = self.base / "cover.webp"
        Image.new("RGB", (8, 8), "green").save(image)
        converted = publish.normalized_image(image, self.base / "converted.png")
        with Image.open(converted) as opened:
            self.assertEqual(opened.format, "PNG")


if __name__ == "__main__":
    unittest.main()
