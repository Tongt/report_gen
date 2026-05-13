from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).parent
KB_DIR = BASE_DIR / "knowledge_base"
SKILLS_DIR = BASE_DIR / "skills"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUTS_DIR = BASE_DIR / "outputs"
CHROMA_DIR = KB_DIR / "chroma_db"
RAW_UPLOADS_DIR = KB_DIR / "raw_uploads"
CONFIG_DIR = BASE_DIR / "config"
USER_SETTINGS_PATH = CONFIG_DIR / "user_settings.json"

COLLECTION_NAME = "wukan_wuding_docs"

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".md", ".txt"}

FIVE_LOOKS = [
    "看宏观",
    "看行业",
    "看客户",
    "看竞争",
    "看自己",
]

FIVE_DECISIONS = [
    "定方向",
    "定目标",
    "定技术",
    "定重大项目",
    "定重大举措",
]


def ensure_dirs() -> None:
    for path in [KB_DIR, SKILLS_DIR, TEMPLATES_DIR, OUTPUTS_DIR, CHROMA_DIR, RAW_UPLOADS_DIR, CONFIG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _invalid_api_key_placeholders() -> set[str]:
    return {
        "请在这里填写你的Qwen API Key",
        "请填写你的Qwen API Key",
        "your_api_key",
        "YOUR_API_KEY",
    }


def _api_key_from_streamlit_secrets() -> str:
    """Streamlit Community Cloud：在应用设置里配置 Secrets（DASHSCOPE_API_KEY）。"""
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return ""
        if "DASHSCOPE_API_KEY" in secrets:
            return str(secrets["DASHSCOPE_API_KEY"] or "").strip()
        return ""
    except Exception:
        return ""


def load_api_key() -> str:
    invalid_placeholders = _invalid_api_key_placeholders()

    secret_key = _api_key_from_streamlit_secrets()
    if secret_key and secret_key not in invalid_placeholders:
        return secret_key

    dot_env_path = BASE_DIR / ".env"
    if dot_env_path.exists():
        load_dotenv(dotenv_path=dot_env_path, override=False)

    env_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if env_key in invalid_placeholders:
        env_key = ""
    if env_key:
        return env_key

    if USER_SETTINGS_PATH.exists():
        try:
            payload = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
            return str(payload.get("dashscope_api_key", "")).strip()
        except Exception:
            return ""
    return ""


def save_user_api_key(api_key: str) -> None:
    ensure_dirs()
    payload = {"dashscope_api_key": api_key.strip()}
    USER_SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def mask_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def load_settings() -> dict[str, str]:
    dot_env_path = BASE_DIR / ".env"
    if dot_env_path.exists():
        load_dotenv(dotenv_path=dot_env_path, override=False)
    api_key = load_api_key()
    chat_model = os.getenv("QWEN_CHAT_MODEL", "qwen-max").strip()
    embedding_model = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4").strip()
    return {
        "api_key": api_key,
        "chat_model": chat_model,
        "embedding_model": embedding_model,
    }
