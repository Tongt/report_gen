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
# Streamlit 等多访客共用磁盘时：每浏览器会话一层子目录，避免互相看见 Key / 向量 / 上传文件
SESSIONS_ROOT = KB_DIR / "sessions"
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
    for path in [
        KB_DIR,
        SKILLS_DIR,
        TEMPLATES_DIR,
        OUTPUTS_DIR,
        CHROMA_DIR,
        RAW_UPLOADS_DIR,
        SESSIONS_ROOT,
        CONFIG_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def storage_paths_for_visitor_session(visitor_session_id: str | None) -> tuple[Path, Path, Path, Path]:
    """返回 (知识库扫描根目录, 上传目录, Chroma 目录, 报告输出目录)。

    visitor_session_id 为 None 时沿用单机布局（knowledge_base 根下的 raw_uploads / chroma_db）。
    """
    if not visitor_session_id:
        return KB_DIR, RAW_UPLOADS_DIR, CHROMA_DIR, OUTPUTS_DIR
    root = SESSIONS_ROOT / visitor_session_id
    raw = root / "raw_uploads"
    chroma = root / "chroma_db"
    out = OUTPUTS_DIR / "sessions" / visitor_session_id
    return root, raw, chroma, out


def is_per_visitor_disk_isolation_enabled(
    *,
    streamlit_secrets_get: object | None = None,
) -> bool:
    """是否在磁盘上为每位访客单独分目录（Streamlit Community Cloud 等多用户共盘场景）。

    显式打开：环境变量或 Streamlit Secrets 中 ``WUKAN_MULTI_TENANT=1``/``true``。
    显式关闭（强制共用旧布局）：``WUKAN_SINGLE_TENANT=1``。
    否则：用常见 Cloud 特征做启发式判断（不保证覆盖所有托管商，可用手动开关兜底）。
    """
    opt_out = os.getenv("WUKAN_SINGLE_TENANT", "").strip().lower() in ("1", "true", "yes")
    if opt_out:
        return False

    opt_in = os.getenv("WUKAN_MULTI_TENANT", "").strip().lower() in ("1", "true", "yes")
    if opt_in:
        return True

    if streamlit_secrets_get is not None:
        try:
            st_val = streamlit_secrets_get("WUKAN_MULTI_TENANT")
            if str(st_val).strip().lower() in ("1", "true", "yes"):
                return True
            if str(st_val).strip().lower() in ("0", "false", "no"):
                return False
        except Exception:
            pass
        try:
            st_single = streamlit_secrets_get("WUKAN_SINGLE_TENANT")
            if str(st_single).strip().lower() in ("1", "true", "yes"):
                return False
        except Exception:
            pass

    if os.getenv("STREAMLIT_SHARING_MODE", "").strip() == "streamlit-community-cloud":
        return True
    if os.getenv("STREAMLIT_CLOUD", "").strip() == "1":
        return True
    hostname = (os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME") or "").lower()
    if hostname.endswith(".streamlit.app"):
        return True
    # 历史容器镜像里常见（可能随平台变更；若未命中请用 Secrets 显式写 WUKAN_MULTI_TENANT）
    if os.getenv("HOME", "").rstrip("/") == "/home/appuser":
        return True
    return False


def _invalid_api_key_placeholders() -> set[str]:
    return {
        "请在这里填写你的Qwen API Key",
        "请填写你的Qwen API Key",
        "your_api_key",
        "YOUR_API_KEY",
    }


def load_api_key() -> str:
    """解析顺序：页面保存的 user_settings → 环境变量（含 .env）。

    不从 Streamlit Deploy Secrets 读取 DASHSCOPE_API_KEY，以便每位使用者填写自己的 Key。
    """
    invalid_placeholders = _invalid_api_key_placeholders()

    if USER_SETTINGS_PATH.exists():
        try:
            payload = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
            user_key = str(payload.get("dashscope_api_key", "")).strip()
            if user_key and user_key not in invalid_placeholders:
                return user_key
        except Exception:
            pass

    dot_env_path = BASE_DIR / ".env"
    if dot_env_path.exists():
        load_dotenv(dotenv_path=dot_env_path, override=False)

    env_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if env_key in invalid_placeholders:
        env_key = ""
    if env_key:
        return env_key

    return ""


def save_user_api_key(api_key: str) -> None:
    ensure_dirs()
    payload = {"dashscope_api_key": api_key.strip()}
    USER_SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_saved_api_key() -> None:
    if USER_SETTINGS_PATH.exists():
        USER_SETTINGS_PATH.unlink()


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
