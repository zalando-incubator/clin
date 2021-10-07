from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import unique, Enum
from typing import Optional


@unique
class Audience(str, Enum):
    COMPONENT_INTERNAL = "component-internal"
    BUSINESS_UNIT_INTERNAL = "business-unit-internal"
    COMPANY_INTERNAL = "company-internal"
    EXTERNAL_PARTNER = "external-partner"
    EXTERNAL_PUBLIC = "external-public"

    def __str__(self) -> str:
        return str(self.value)


@unique
class Category(str, Enum):
    BUSINESS = "business"
    DATA = "data"
    UNDEFINED = "undefined"

    def __str__(self) -> str:
        return str(self.value)


@unique
class Kind(str, Enum):
    EVENT_TYPE = "event-type"
    SQL_QUERY = "sql-query"
    SUBSCRIPTION = "subscription"

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class EventOwnerSelector:
    @unique
    class Type(str, Enum):
        PATH = "path"
        STATIC = "static"

        def __str__(self) -> str:
            return str(self.value)

    type: Type
    name: str
    value: str

    @staticmethod
    def from_spec(spec: dict[str, any]) -> EventOwnerSelector:
        return EventOwnerSelector(
            type=EventOwnerSelector.Type(spec["type"]),
            name=spec["name"],
            value=spec["value"],
        )

    def to_spec(self) -> dict[str, any]:
        return {"type": str(self.type), "name": self.name, "value": self.value}


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
    def from_spec(spec: dict[str, any]) -> Cleanup:
        return Cleanup(
            policy=Cleanup.Policy(spec["policy"]),
            retention_time_days=spec.get(
                "retentionTimeDays", 1  # 1 is default Nakadi value
            ),
        )

    def to_spec(self) -> dict[str, any]:
        return {
            "policy": str(self.policy),
            "retentionTimeDays": self.retention_time_days,
        }


@dataclass
class Partitioning:
    @unique
    class Strategy(str, Enum):
        USER_DEFINED = "user_defined"
        HASH = "hash"
        RANDOM = "random"

        def __str__(self) -> str:
            return str(self.value)

    strategy: Strategy
    keys: list[str]
    partition_count: int

    @staticmethod
    def from_spec(spec: dict[str, any]) -> Partitioning:
        return Partitioning(
            strategy=Partitioning.Strategy(spec["strategy"]),
            keys=spec.get("keys", []),
            partition_count=spec["partitionCount"],
        )

    def to_spec(self) -> dict[str, any]:
        return {
            "strategy": str(self.strategy),
            "keys": self.keys,
            "partitionCount": self.partition_count,
        }


@dataclass
class Schema:
    @unique
    class Compatibility(str, Enum):
        NONE = "none"
        FORWARD = "forward"
        COMPATIBLE = "compatible"

        def __str__(self) -> str:
            return str(self.value)

    compatibility: Compatibility
    json_schema: dict[str, any]

    @staticmethod
    def from_spec(spec: dict[str, any]) -> Schema:
        return Schema(
            compatibility=Schema.Compatibility(spec["compatibility"]),
            json_schema=spec["jsonSchema"],
        )

    def to_spec(self) -> dict[str, any]:
        return {
            "compatibility": str(self.compatibility),
            "jsonSchema": self.json_schema,
        }


@dataclass
class Envelope:
    kind: Kind
    spec: dict[str, any]

    @staticmethod
    def from_manifest(manifest: dict[str, any]) -> Envelope:
        if "kind" not in manifest:
            raise ValueError("Required field `kind` not found")
        if "spec" not in manifest:
            raise ValueError(f"Required field `spec` not found")

        return Envelope(kind=Kind(manifest["kind"]), spec=manifest["spec"])

    def to_manifest(self) -> dict[str, any]:
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
    def to_spec(self) -> dict[str, any]:
        pass

    def to_envelope(self) -> Envelope:
        return Envelope(kind=self.kind, spec=self.to_spec())
