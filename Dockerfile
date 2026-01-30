FROM python:3.11-slim

# 让日志更即时、少缓存
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 系统依赖（按需增减；一般够用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# 先拷贝依赖文件（利用缓存）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 再拷贝代码
COPY . /app

# entrypoint
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

# 用 entrypoint 先迁移再启动
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# Gunicorn 多 worker 更适合服务器
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
