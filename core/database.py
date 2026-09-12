from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import inspect, text
from config import settings
import os

# Connect SQLite engine with check_same_thread=False for FastAPI concurrency
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Columns added after the initial release. create_all() only creates missing
# tables, not missing columns on existing tables, so an existing insta_auto.db
# needs these added by hand on startup.
_COLUMN_MIGRATIONS = {
    "automationrule": {
        "target_media_id": "VARCHAR",
        "target_media_permalink": "VARCHAR",
        "public_reply_enabled": "BOOLEAN DEFAULT 0",
        "public_reply_text": "VARCHAR",
    },
}

def _run_column_migrations():
    if "sqlite" not in settings.DATABASE_URL:
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            if table not in existing_tables:
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            for column, coltype in columns.items():
                if column not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))

def init_db():
    SQLModel.metadata.create_all(engine)
    _run_column_migrations()
    # Seed default sample rule if empty
    with Session(engine) as session:
        existing = session.exec(select(SQLModel.metadata.tables['automationrule'])).first()
        if not existing:
            from core.models import AutomationRule
            sample_rule = AutomationRule(
                name="Welcome VIP Guide (Sample)",
                keywords='["guide", "ebook", "freebie"]',
                match_type="contains",
                rule_type="all",
                response_text="Hey! Thanks for reaching out! Here is your exclusive Creator Playbook link: https://example.com/creator-guide 🚀 Enjoy!",
                follow_gate_enabled=True,
                follow_gate_message="Hey! 👋 We love sharing our free resources with our community. Please follow @ourpage first, then send 'GUIDE' again to receive your free download instantly! ✨",
                cooldown_minutes=60,
                is_active=True
            )
            session.add(sample_rule)
            session.commit()

def get_session():
    with Session(engine) as session:
        yield session
