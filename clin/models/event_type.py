from __future__ import annotations

from dataclasses import dataclass

from colorama import Fore

from clin.models.auth import ReadWriteAuth
from clin.models.shared import (
    Cleanup,
    Category,
    Entity,
    Kind,
    Audience,
    Partitioning,
    Schema,
)


@dataclass
class EventType(Entity):
    name: str
    category: Category
    owning_application: str
    audience: Audience
    partitioning: Partitioning
    cleanup: Cleanup
    schema: Schema
    auth: ReadWriteAuth

    def __str__(self) -> str:
        return f"event type {Fore.BLUE}{self.name}{Fore.RESET}"

    @property
    def kind(self) -> Kind:
        return Kind.EVENT_TYPE

    @staticmethod
    def from_spec(spec: dict[str, any]) -> EventType:
        return EventType(
            name=spec["name"],
            category=Category(spec["category"]),
            owning_application=spec["owningApplication"],
            audience=Audience(spec["audience"]),
            partitioning=Partitioning.from_spec(spec["partitioning"]),
            cleanup=Cleanup.from_spec(spec["cleanup"]),
            schema=Schema.from_spec(spec["schema"]),
            auth=ReadWriteAuth.from_spec(spec["auth"]),
        )

    def to_spec(self) -> dict[str, any]:
        return {
            "name": self.name,
            "category": str(self.category),
            "owningApplication": self.owning_application,
            "audience": str(self.audience),
            "partitioning": self.partitioning.to_spec(),
            "cleanup": self.cleanup.to_spec(),
            "schema": self.schema.to_spec(),
            "auth": self.auth.to_spec() if self.auth else {},
        }
