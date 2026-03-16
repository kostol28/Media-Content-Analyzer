import os


class Settings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./media_analyzer.db")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.app_name = "Media Content Analyzer"
        self.request_timeout_seconds = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))


settings = Settings()
