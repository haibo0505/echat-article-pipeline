"""Side-effect-free configuration for the combined WeChat skill."""

from __future__ import annotations

import json
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def config_path() -> Path:
    override = os.environ.get("WECHAT_PIPELINE_CONFIG")
    return Path(override).expanduser().resolve() if override else SKILL_DIR / "config.json"


def default_data_dir() -> Path:
    override = os.environ.get("WECHAT_PIPELINE_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt" and Path("D:/").is_dir():
        return Path("D:/APP/wechat-article-pipeline-data")
    return Path.cwd() / "wechat-output"


def load_config() -> dict:
    base = default_data_dir()
    result = {
        "output_dir": str(base / "rendered"),
        "vault_root": str(Path.cwd()),
        "cache_dir": str(base / "cache"),
        "image_search_paths": [],
        "settings": {"default_theme": "newspaper", "auto_open_browser": False, "header_author_label": ""},
        "wechat": {"app_id": "", "app_secret": "", "author": ""},
    }
    path = config_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("配置文件必须是 JSON 对象")
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key].update(value)
            elif value not in (None, ""):
                result[key] = value
        for key in ("output_dir", "vault_root", "cache_dir"):
            candidate = Path(os.path.expandvars(str(result[key]))).expanduser()
            result[key] = str(candidate if candidate.is_absolute() else (path.parent / candidate).resolve())
    for field, variable in (("app_id", "WECHAT_APP_ID"), ("app_secret", "WECHAT_APP_SECRET"), ("author", "WECHAT_AUTHOR")):
        if os.environ.get(variable):
            result["wechat"][field] = os.environ[variable]
    return result


def cache_dir(config: dict | None = None) -> Path:
    return Path((config or load_config())["cache_dir"])


def configure_console() -> None:
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
