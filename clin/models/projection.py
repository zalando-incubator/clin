from __future__ import annotations

from dataclasses import dataclass

from colorama import Fore

from clin.models.auth import Auth
from clin.models.shared import Cleanup, Category, Entity, Kind


@dataclass
class OutputEventType:
    category: Category
    cleanup: Cleanup


@dataclass
class Projection(Entity):
    name: str
    sql: str
    envelope: bool
    output_event_type: OutputEventType
    auth: Auth

    def __str__(self) -> str:
        return f"projection {Fore.BLUE}{self.name}{Fore.RESET}"

    @property
    def kind(self) -> Kind:
        return Kind.PROJECTION

    @staticmethod
    def from_spec(spec: dict) -> Projection:
        return Projection(
            name=spec["name"],
            sql=spec["sql"],
            envelope=spec["envelope"],
            output_event_type=OutputEventType(
                category=Category(spec["output_event_type"]["category"]),
                cleanup=Cleanup.from_spec(spec["output_event_type"]["cleanup"]),
            ),
            auth=Auth.from_spec(spec["auth"]),
        )

    def to_spec(self) -> dict:
        return {
            "name": self.name,
            "sql": self.sql,
            "envelope": self.envelope,
            "output_event_type": {
                "category": str(self.output_event_type.category),
                "cleanup": self.output_event_type.cleanup.to_spec(),
            },
            "auth": self.auth.to_spec() if self.auth else {},
        }
