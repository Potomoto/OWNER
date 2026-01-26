# Notes API - AI-Powered Note Management System

基于 FastAPI + SQLite + DeepSeek AI 的笔记管理服务，支持笔记的CRUD操作和AI摘要/改写功能。

## 功能特性

✅ 笔记 CRUD 操作（创建、查询、更新、删除）
✅ 笔记分页和排序
✅ AI 摘要功能（支持多版本Prompt）
✅ AI 改写功能（支持自定义风格）
✅ X-API-Key 认证
✅ 完整的 OpenAPI 文档 (Swagger UI)
✅ SQLite 数据库 + Alembic 迁移管理
✅ 单元测试覆盖（pytest）

## 快速开始

### 1. 环境配置（Windows PowerShell）

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖（如果还未安装）
pip install -r requirements.txt
```

### 2. 配置文件

推荐使用 .env 文件管理配置：

```powershell
# 复制示例配置
Copy-Item .env.example .env

# 编辑 .env（根据需要修改以下配置）
# API_KEY=your-api-key-here
# DATABASE_URL=sqlite:///./notes.db
# DEEPSEEK_API_KEY=your-deepseek-key
# ENV=dev
```

或者直接设置环境变量：

```powershell
$env:API_KEY="dev-key-123"
$env:ENV="dev"
```

### 3. 启动开发服务器

```powershell
uvicorn app.main:app --reload
```

服务器运行在 http://127.0.0.1:8000

查看 Swagger UI 文档：http://127.0.0.1:8000/docs

## API 使用示例

### 认证

所有请求需要在 Header 中提供 API Key：

```powershell
# PowerShell
$headers = @{"X-API-Key" = "dev-key-123"}
```

### 笔记操作

```powershell
# 创建笔记
$body = @{
    title = "我的笔记"
    content = "这是笔记内容"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://127.0.0.1:8000/v1/notes" `
    -Method POST `
    -Headers @{"X-API-Key" = "dev-key-123"; "Content-Type" = "application/json"} `
    -Body $body

# 查询笔记列表
Invoke-WebRequest -Uri "http://127.0.0.1:8000/v1/notes?limit=20&offset=0&sort=created_at_desc" `
    -Headers @{"X-API-Key" = "dev-key-123"}

# 获取单个笔记
Invoke-WebRequest -Uri "http://127.0.0.1:8000/v1/notes/1" `
    -Headers @{"X-API-Key" = "dev-key-123"}

# 更新笔记
$body = @{
    title = "更新后的标题"
    content = "更新后的内容"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://127.0.0.1:8000/v1/notes/1" `
    -Method PUT `
    -Headers @{"X-API-Key" = "dev-key-123"; "Content-Type" = "application/json"} `
    -Body $body

# 删除笔记
Invoke-WebRequest -Uri "http://127.0.0.1:8000/v1/notes/1" `
    -Method DELETE `
    -Headers @{"X-API-Key" = "dev-key-123"}
```

### AI 功能

```powershell
# 摘要笔记内容
$body = @{
    content = "很长的笔记文本..."
    prompt_key = "summarize_v1"  # 可选，默认为 summarize_v1
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://127.0.0.1:8000/ai/summarize" `
    -Method POST `
    -Headers @{"X-API-Key" = "dev-key-123"; "Content-Type" = "application/json"} `
    -Body $body

# 改写笔记内容（支持自定义风格）
$body = @{
    content = "原始内容"
    style = "专业学术风格"
    prompt_key = "rewrite_v1"  # 可选
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://127.0.0.1:8000/ai/rewrite" `
    -Method POST `
    -Headers @{"X-API-Key" = "dev-key-123"; "Content-Type" = "application/json"} `
    -Body $body
```

## 开发工作流

### 运行测试

```powershell
# 运行所有测试
python -m pytest -v

# 运行单个测试文件
python -m pytest tests/test_notes.py -v

# 快速运行（简洁输出）
python -m pytest -q
```

### 数据库迁移

首次创建表或修改模型后：

```powershell
# 1. 生成迁移脚本（自动检测变更）
alembic revision --autogenerate -m "描述你的变更"

# 2. 应用迁移到数据库
alembic upgrade head

# 查看迁移历史
alembic history

# 回滚到上一个版本（如需）
alembic downgrade -1
```

**注意**：生产环境必须使用 Alembic 迁移，不要依赖 `create_all()`。开发环境中 `main.py` 会在启动时自动建表（学习阶段方便）。

### 代码格式和检查

项目使用 Ruff 进行代码检查和格式化：

```powershell
# 检查代码问题
ruff check app/

# 自动修复可修复的问题
ruff check --fix app/

# 代码格式化
ruff format app/
```

# 记忆功能测试
$headers = @{ "X-API-Key" = "dev-key-123" }
$bodyObj = @{
  request   = "请创建一条标题为Session23的笔记，内容为：我已经接入了SQLite记忆。"
  max_steps = 5
  debug     = $true
}
$body = $bodyObj | ConvertTo-Json -Depth 20 -Compress   # ✅ 一定要加 -Depth

$raw1 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/ai/agent/run" `
  -Headers $headers -ContentType "application/json; charset=utf-8" -Body $body
# ✅ 强制拿到 thread_id 的纯字符串
$threadId = [string]$raw1.thread_id
$threadId


$state = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/ai/agent/state/{0}" -f $threadId) `
  -Headers $headers
# 打印关键字段
$state.steps_count
$state.last_action | ConvertTo-Json -Depth 20


$body2Obj = @{
  request   = "继续：请搜索Session23相关笔记，并告诉我找到几个。"
  thread_id = $threadId         # ✅ 用纯字符串变量，不要直接 $r.thread_id
  max_steps = 5
  debug     = $true
}
$body2 = $body2Obj | ConvertTo-Json -Depth 20 -Compress
$raw2 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/ai/agent/run" `
  -Headers $headers -ContentType "application/json; charset=utf-8" -Body $body2
$raw2 | ConvertTo-Json -Depth 20

## 项目结构

```
notes-api/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── settings.py             # 配置管理
│   ├── db.py                   # 数据库连接和会话
│   ├── models.py               # SQLAlchemy 模型定义
│   ├── security.py             # API Key 认证
│   │
│   ├── routers/                # API 路由
│   │   ├── notes.py            # 笔记 CRUD 端点
│   │   └── ai.py               # AI 功能端点
│   │
│   ├── services/               # 业务逻辑层
│   │   └── notes_service.py    # 笔记业务逻辑
│   │
│   ├── ai/                     # AI 功能模块
│   │   ├── ai_service.py       # AI 编排逻辑
│   │   ├── deepseek_client.py  # DeepSeek API 客户端
│   │   ├── output_schemas.py   # 输出数据结构
│   │   ├── prompt_registry.py  # Prompt 版本注册表
│   │   └── prompt_render.py    # Prompt 模板渲染
│   │
│   ├── schemas/                # Pydantic 数据验证
│   │   └── notes.py            # 笔记请求/响应模式
│   │
│   ├── prompts/                # AI Prompt 模板
│   │   ├── summarize_v1.txt
│   │   ├── summarize_v1b.txt
│   │   ├── rewrite_v1.txt
│   │   ├── qa_v1.txt
│   │   └── tool_select_v1.txt
│   │
│   └── core/                   # 核心模块
│       ├── errors.py           # 异常处理
│       ├── logging.py          # 日志配置
│       └── middleware.py       # 中间件
│
├── tests/                      # 单元测试
│   ├── conftest.py             # pytest 配置和 fixtures
│   ├── test_notes.py           # 笔记 API 测试
│   └── test_prompts.py         # Prompt 功能测试
│
├── alembic/                    # 数据库迁移脚本
├── .env.example                # 环境变量示例
├── pyproject.toml              # 项目配置（Ruff等）
├── requirements.txt            # Python 依赖
└── README.txt                  # 本文件
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| ENV | dev | 运行环境（dev/prod） |
| API_KEY | - | API 认证密钥（必填） |
| DATABASE_URL | sqlite:///./notes.db | 数据库连接字符串 |
| DEEPSEEK_API_KEY | - | DeepSeek API 密钥（使用AI功能必填） |
| DEEPSEEK_BASE_URL | https://api.siliconflow.cn/v1 | DeepSeek API 基础URL |
| DEEPSEEK_MODEL | deepseek-ai/DeepSeek-R1-0528-Qwen3-8B | 使用的模型 |

## 故障排除

### 数据库错误
```
如果遇到数据库错误，可以删除 notes.db 文件，重启服务器会自动重建：
Remove-Item notes.db -ErrorAction SilentlyContinue
```

### API Key 未配置
```
确保在 .env 文件或环境变量中设置了 API_KEY
$env:API_KEY="your-key"
```

### DeepSeek API 失败
```
1. 检查 DEEPSEEK_API_KEY 是否正确设置
2. 检查网络连接
3. 查看日志信息：日志中会记录请求耗时和错误信息（不包含具体内容，保护隐私）
```

## 技术栈

- **框架**: FastAPI + SQLAlchemy + Pydantic
- **数据库**: SQLite（开发），支持切换到其他数据库
- **AI**: DeepSeek API（JSON 模式）
- **迁移**: Alembic
- **测试**: pytest
- **代码质量**: Ruff（linting + formatting）


