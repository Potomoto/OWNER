from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app import settings

# 定义：我们从请求 Header 的 X-API-Key 里取值
# APIKeyHeader会将需要X-API-Key的项目规则写入OpenAPI文档
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# verify_api_key是一个依赖，FastAPI会在每一个请求前先执行它
def verify_api_key(api_key: str | None = Depends(api_key_header)) -> None:
    """
    鉴权依赖：
    - 读取环境变量 API_KEY 作为“正确的钥匙”
    - 读取请求头 X-API-Key 作为“用户提交的钥匙”
    - 不匹配就 401
    """
    expected = settings.API_KEY

    # 学习阶段：如果你忘了设置 API_KEY，直接报错提醒
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY is not configured on server")

    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
