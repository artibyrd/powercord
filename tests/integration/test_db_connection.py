import pytest
from sqlmodel import Field, Session, SQLModel, select

# All tests in this module are integration tests.
pytestmark = pytest.mark.integration


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None


def test_create_hero(session: Session):
    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    session.add(hero_1)
    session.commit()
    session.refresh(hero_1)
    assert hero_1.id is not None
    assert hero_1.name == "Deadpond"


def test_read_hero(session: Session):
    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    session.add(hero_1)
    session.commit()

    hero_2 = session.exec(select(Hero).where(Hero.name == "Deadpond")).first()
    assert hero_2 is not None
    assert hero_2.secret_name == "Dive Wilson"
