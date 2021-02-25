from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import unique, Enum


@unique
class Category(str, Enum):
    BUSINESS = "business"
    DATA = "data"
    UNDEFINED = "undefined"

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class Cleanup:
    @unique
    class Policy(str, Enum):
        DELETE = "delete"
        COMPACT = "compact"

        def __str__(self) -> str:
            return str(self.value)

    policy: Policy
    retention_time_days: int

    @staticmethod
    def from_spec(spec: dict) -> Cleanup:
        return Cleanup(
            policy=Cleanup.Policy(spec["policy"]),
            retention_time_days=spec.get(
                "retentionTimeDays", 1  # 1 is default Nakadi value
            ),
        )

    def to_spec(self) -> dict:
        return {
            "policy": str(self.policy),
            "retentionTimeDays": self.retention_time_days,
        }


@unique
class Kind(str, Enum):
    EVENT_TYPE = "event-type"
    PROJECTION = "projection"
    SUBSCRIPTION = "subscription"

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class Envelope:
    kind: Kind
    spec: dict

    @staticmethod
    def from_manifest(manifest: dict) -> Envelope:
        if "kind" not in manifest:
            raise ValueError("Required field `kind` not found")
        if "spec" not in manifest:
            raise ValueError(f"Required field `spec` not found")

        return Envelope(kind=Kind(manifest["kind"]), spec=manifest["spec"])

    def to_manifest(self) -> dict:
        return {
            "kind": str(self.kind),
            "spec": self.spec,
        }


class Entity(ABC):
    @property
    @abstractmethod
    def kind(self) -> Kind:
        pass

    @abstractmethod
    def to_spec(self) -> dict:
        pass

    def to_envelope(self) -> Envelope:
        return Envelope(kind=self.kind, spec=self.to_spec())
