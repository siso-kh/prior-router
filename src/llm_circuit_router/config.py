from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    NARA_API_KEY: str
    NARA_BASE_URL: str

    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str 

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
