from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite 数据库文件：notes.db（在项目根目录）
DATABASE_URL = "sqlite:///./notes.db"

# engine:数据库的发动，负责连接数据库
# SQLite 在多线程环境下需要这个参数（FastAPI 常见）
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Session工厂，随时创建新的session
# session是与数据库之间的一次对话窗口，每次操作后需要关闭（避免资源泄露）
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass

# 让FastAPI每次请求自动创建/关闭session
def get_db():
    """
    FastAPI 依赖：每次请求来 -> 创建一个 Session
    请求结束 -> 关闭 Session
    """
    db = SessionLocal() # 资源初始化
    try:
        yield db        # 资源注入
    finally:
        db.close()      # 资源释放
