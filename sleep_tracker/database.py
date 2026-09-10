"""Подключение к БД: engine, фабрика сессий и Base для ORM-моделей.

Адрес берётся из переменной SLEEPTRACK_DATABASE_URL. В Docker Compose это PostgreSQL,
а при локальном запуске по умолчанию используется файл SQLite в текущей папке —
история работает сразу, без установки Postgres.

БД нужна только для истории. Поэтому таблицы создаются лениво, при первом обращении
(ensure_schema), а не жёстко на старте: если база недоступна, приложение всё равно
поднимется и будет считать оценку сна без сохранения.
"""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("SLEEPTRACK_DATABASE_URL", "sqlite:///./sleeptrack.db")


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # FastAPI выполняет обычные (def) роуты в пуле потоков, а SQLite по умолчанию
        # запрещает пользоваться соединением из другого потока.
        connect_args = {"check_same_thread": False}
    else:
        # Если Postgres лежит, лучше быстро получить ошибку, чем висеть на запросе.
        connect_args = {"connect_timeout": 3}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Базы, в которых таблицы уже точно созданы — чтобы не дёргать create_all на каждый запрос.
_schema_ready: set[Engine] = set()


def ensure_schema(session: Session) -> None:
    """Создаёт таблицы при первом обращении к этой БД; дальше ничего не делает.

    Бросает SQLAlchemyError, если база недоступна, — вызывающий код решает,
    работать без истории или вернуть ошибку.
    """
    bind = session.get_bind()
    if bind in _schema_ready:
        return
    from . import models  # noqa: F401 — импорт регистрирует таблицы в Base.metadata

    Base.metadata.create_all(bind)
    _schema_ready.add(bind)


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость: одна сессия на запрос. Соединение открывается только при первом запросе к БД."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
