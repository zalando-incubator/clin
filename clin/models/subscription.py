from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from colorama import Fore

from clin.models.auth import Auth


@dataclass
class Subscription:
    id: Optional[UUID]
    owning_application: str
    event_types: List[str]
    consumer_group: str
    auth: Auth

    def __str__(self) -> str:
        prefix = f"subscription"
        if self.id:
            prefix += f" {Fore.BLUE}{self.id}{Fore.RESET}"
        return f"{prefix} ({Subscription.components_string(self.event_types, self.owning_application, self.consumer_group)})"

    @staticmethod
    def from_spec(spec: dict) -> Subscription:
        return Subscription(
            id=None,
            owning_application=spec["owningApplication"],
            event_types=spec["eventTypes"],
            consumer_group=spec["consumerGroup"],
            auth=Auth.from_spec(spec["auth"]),
        )

    @staticmethod
    def components_string(
        event_types: List[str], owning_application: str, consumer_group: str
    ):
        return f"event type(s): '{', '.join(event_types)}'; application: '{owning_application}'; consumer group: '{consumer_group}'"
