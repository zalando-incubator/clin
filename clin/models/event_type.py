from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from colorama import Fore

from clin.models.auth import ReadWriteAuth
from clin.models.shared import (
    Cleanup,
    Category,
    Entity,
    EventOwnerSelector,
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
    event_owner_selector: Optional[EventOwnerSelector]

    def __str__(self) -> str:
        return f"event type {Fore.BLUE}{self.name}{Fore.RESET}"

    @property
    def kind(self) -> Kind:
        return Kind.EVENT_TYPE

    @staticmethod
    def from_spec(spec: dict[str, any]) -> EventType:
        def maybe_event_owner_selector():
            maybe = spec.get("eventOwnerSelector", None)
            return EventOwnerSelector.from_spec(maybe) if maybe else None

        return EventType(
            name=spec["name"],
            category=Category(spec["category"]),
            owning_application=spec["owningApplication"],
            audience=Audience(spec["audience"]),
            partitioning=Partitioning.from_spec(spec["partitioning"]),
            cleanup=Cleanup.from_spec(spec["cleanup"]),
            schema=Schema.from_spec(spec["schema"]),
            auth=ReadWriteAuth.from_spec(spec["auth"]),
            event_owner_selector=maybe_event_owner_selector(),
        )

    def to_spec(self) -> dict[str, any]:
        def maybe_event_owner_selector():
            return (
                self.event_owner_selector.to_spec()
                if self.event_owner_selector
                else None
            )

        return {
            "name": self.name,
            "category": str(self.category),
            "owningApplication": self.owning_application,
            "audience": str(self.audience),
            "partitioning": self.partitioning.to_spec(),
            "cleanup": self.cleanup.to_spec(),
            "schema": self.schema.to_spec(),
            "auth": self.auth.to_spec() if self.auth else {},
            "eventOwnerSelector": maybe_event_owner_selector(),
        }
