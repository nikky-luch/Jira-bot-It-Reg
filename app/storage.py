from __future__ import annotations
import os, datetime as dt
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime, select
from sqlalchemy.orm import DeclarativeBase, Session, Mapped, mapped_column

DB_PATH = os.getenv("DB_PATH", "/data/bot.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    tg_username: Mapped[Optional[str]] = mapped_column(String(255))
    dept: Mapped[Optional[str]] = mapped_column(String(255))
    jira_username: Mapped[Optional[str]] = mapped_column(String(255))
    subscribed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

Base.metadata.create_all(engine)

def upsert_user(tg_id: int, tg_username: Optional[str]) -> User:
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.tg_id == tg_id))
        if not u:
            u = User(tg_id=tg_id, tg_username=tg_username, subscribed=True)
            s.add(u)
            s.commit()
            s.refresh(u)
        else:
            if tg_username and u.tg_username != tg_username:
                u.tg_username = tg_username
                s.commit()
        return u

def set_dept(tg_id: int, dept: str) -> None:
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.tg_id == tg_id))
        if not u:
            return
        u.dept = dept
        s.commit()

def set_jira_username(tg_id: int, jira_username: str) -> None:
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.tg_id == tg_id))
        if not u:
            return
        u.jira_username = jira_username
        s.commit()

def get_users_by_dept(dept: str):
    with Session(engine) as s:
        return list(s.scalars(select(User).where(User.dept == dept, User.subscribed == True)).all())

def get_user(tg_id: int):
    with Session(engine) as s:
        return s.scalar(select(User).where(User.tg_id == tg_id))
