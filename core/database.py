from sqlmodel import SQLModel, create_engine, Session, select
from config import settings
import os

# Connect SQLite engine with check_same_thread=False for FastAPI concurrency
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

def init_db():
    SQLModel.metadata.create_all(engine)
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
