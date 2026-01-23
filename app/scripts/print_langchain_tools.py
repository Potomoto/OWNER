import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import settings
from app.ai.tools.langchain_adapter import build_langchain_tools


def main():
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = SessionLocal()
    try:
        tools = build_langchain_tools(db)
        for t in tools:
            schema = None
            if getattr(t, "args_schema", None) is not None:
                # Pydantic v2
                schema = t.args_schema.model_json_schema()

            print("=" * 60)
            print("name:", t.name)
            print("description:", t.description)
            print("args_schema:", json.dumps(schema, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
