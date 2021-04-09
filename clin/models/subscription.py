from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from colorama import Fore

from clin.models.auth import ReadOnlyAuth
from clin.models.shared import Kind, Entity


@dataclass
class Subscription(Entity):
    id: Optional[UUID]
    owning_application: str
    event_types: list[str]
    consumer_group: str
    auth: ReadOnlyAuth

    def __str__(self) -> str:
        prefix = f"subscription"
        if self.id:
            prefix += f" {Fore.BLUE}{self.id}{Fore.RESET}"
        return f"{prefix} ({Subscription.components_string(self.event_types, self.owning_application, self.consumer_group)})"

    @property
    def kind(self) -> Kind:
        return Kind.SUBSCRIPTION

    @staticmethod
    def from_spec(spec: dict[str, any]) -> Subscription:
        return Subscription(
            id=None,
            owning_application=spec["owningApplication"],
            event_types=spec["eventTypes"],
            consumer_group=spec["consumerGroup"],
            auth=ReadOnlyAuth.from_spec(spec["auth"]),
        )

    @staticmethod
    def components_string(
        event_types: list[str],
        owning_application: str,
        consumer_group: str,
    ):
        return (
            f"event type(s): '{', '.join(event_types)}';"
            f" application: '{owning_application}';"
            f" consumer group: '{consumer_group}'"
        )

    def to_spec(self) -> dict[str, any]:
        raise NotImplementedError()
