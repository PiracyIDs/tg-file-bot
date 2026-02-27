from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    default_download_limit: int = 0

print(Settings(_env_file=None, default_download_limit=""))
