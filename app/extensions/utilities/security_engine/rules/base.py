"""Base security rule specification."""

from sqlmodel import Session


class SecurityRule:
    name: str = ""
    category: str = ""
    severity: str = ""

    def evaluate(self, guild_id: int, session: Session) -> list[dict]:
        raise NotImplementedError
