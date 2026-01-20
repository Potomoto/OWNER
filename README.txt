# 项目简介：NotesAPI(FateAPI + SQLite + API Key + pytest)

# 本地启动：使用Windows PowerShell启动
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
进入http://127.0.0.1:8000/docs

# Windows PowerShell 先设置环境变量（开发阶段）
$env:API_KEY="dev-key-123"

# 带 API Key 调用
curl "http://127.0.0.1:8000/v1/notes" -H "X-API-Key: dev-key-123"

# 测试 python -m pytest -q

# 推荐：使用 .env（开发更省事）
1）复制 .env.example 为 .env
2）修改 .env 里的 API_KEY / DATABASE_URL
3）启动：
uvicorn app.main:app --reload

# 数据库迁移 生产环境/团队协作以 Alembic 迁移为准，不依赖 create_all。
alembic revision --autogenerate -m "xxx"
alembic upgrade head


