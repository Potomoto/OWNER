# tests/conftest.py
import os
import sys
from pathlib import Path

# 1) 把项目根目录加到 Python 导入路径里
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 2) 在导入 app 之前就设置环境变量（非常关键）
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_notes.db")
