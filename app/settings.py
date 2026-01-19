# app/settings.py
import os
from dotenv import load_dotenv

# 1) 自动加载项目根目录的 .env
# 默认 override=False：如果系统环境变量已设置，就不会被 .env 覆盖（测试里很有用）
load_dotenv()

ENV = os.getenv("ENV", "dev")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notes.db")
API_KEY = os.getenv("API_KEY")
