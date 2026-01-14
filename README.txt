# Windows PowerShell 先设置环境变量（开发阶段）
$env:API_KEY="dev-key-123"

# 带 API Key 调用
curl "http://127.0.0.1:8000/v1/notes" -H "X-API-Key: dev-key-123"