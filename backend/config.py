"""全局配置：读取 .env，决定是否处于 Mock 模式。"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings:
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    PORT = int(os.getenv("PORT", "8000"))
    FORCE_MOCK = os.getenv("FORCE_MOCK", "false").lower() in ("1", "true", "yes")
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

    # Coze 工作流（外部 Tool）
    COZE_API_BASE = os.getenv("COZE_API_BASE", "https://api.coze.cn").rstrip("/")
    COZE_API_TOKEN = os.getenv("COZE_API_TOKEN", "").strip()
    COZE_WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID", "").strip()
    COZE_TIMEOUT = float(os.getenv("COZE_TIMEOUT", "60"))

    @property
    def mock_mode(self) -> bool:
        """未配置 API Key 或显式开启 FORCE_MOCK 时，进入 Mock 模式，保证项目可演示。"""
        return self.FORCE_MOCK or not self.LLM_API_KEY


settings = Settings()
