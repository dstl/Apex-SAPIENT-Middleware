from datetime import datetime
from typing import Optional

from sqlalchemy import Engine, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.schema import ForeignKey


class SQLBase(DeclarativeBase):
    pass


class Event(SQLBase):
    __tablename__ = "Event"
    id: Mapped[int] = mapped_column(primary_key=True)
    is_sent: Mapped[bool]
    event_date: Mapped[datetime]
    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    json: Mapped[str] = mapped_column(String(20480))


class Scenario(SQLBase):
    __tablename__ = "Scenario"
    id: Mapped[int] = mapped_column(primary_key=True)
    create_date: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    name: Mapped[str]
    delay_start: Mapped[float]
    tasks_per_sec: Mapped[float]
    duration: Mapped[float]
    max_tasks: Mapped[int]
    parameters: Mapped[str]


_ENGINE: Optional[Engine] = None


def get_engine(url: str) -> Engine:
    global _ENGINE

    if _ENGINE is not None:
        return _ENGINE

    if ":///" not in url:
        return get_engine(f"sqlite:///{url}")

    _ENGINE = create_engine(url, echo=False)
    SQLBase.metadata.create_all(_ENGINE)

    return _ENGINE
