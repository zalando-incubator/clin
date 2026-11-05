from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    annotations: Optional[dict[str, str]] = None
    read_from: str = "end"
    initial_cursors: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        prefix = f"subscription"
        if self.id:
            prefix += f" {Fore.BLUE}{self.id}{Fore.RESET}"
        return f"{prefix} ({Subscription.components_string(self.event_types, self.owning_application, self.consumer_group)})"

    @property
    def kind(self) -> Kind:
        return Kind.SUBSCRIPTION

    def for_comparison_with(self, current: Subscription) -> Subscription:
        return replace(
            self,
            annotations=current.annotations
            if self.annotations is None
            else self.annotations,
        )

    @staticmethod
    def from_spec(spec: dict[str, any]) -> Subscription:
        annotations = spec.get("annotations")
        if "annotations" in spec:
            validate_annotations(annotations)
        return Subscription(
            id=None,
            owning_application=spec["owningApplication"],
            event_types=spec["eventTypes"],
            consumer_group=spec["consumerGroup"],
            auth=ReadOnlyAuth.from_spec(spec["auth"]),
            annotations=annotations,
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


def validate_annotations(annotations):
    if not isinstance(annotations, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in annotations.items()
    ):
        raise ValueError(
            "Subscription annotations must be a map of string keys and values; quote numeric values"
        )
