from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Optional, List, Dict

from colorama import Fore

from clin.models.auth import Auth


@unique
class Category(str, Enum):
    BUSINESS = "business"
    DATA = "data"
    UNDEFINED = "undefined"

    def __str__(self) -> str:
        return str(self.value)


@unique
class Audience(str, Enum):
    COMPONENT_INTERNAL = "component-internal"
    BUSINESS_UNIT_INTERNAL = "business-unit-internal"
    COMPANY_INTERNAL = "company-internal"
    EXTERNAL_PARTNER = "external-partner"
    EXTERNAL_PUBLIC = "external-public"

    def __str__(self) -> str:
        return str(self.value)


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
    keys: Optional[List[str]]
    partition_count: int


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
    json_schema: Dict


@dataclass
class EventType:
    name: str
    category: Category
    owning_application: str
    audience: Audience
    partitioning: Partitioning
    cleanup: Cleanup
    schema: Schema
    auth: Auth

    def __str__(self) -> str:
        return f"event type {Fore.BLUE}{self.name}{Fore.RESET}"

    @staticmethod
    def from_spec(spec: dict) -> EventType:
        return EventType(
            name=spec["name"],
            category=Category(spec["category"]),
            owning_application=spec["owningApplication"],
            audience=Audience(spec["audience"]),
            partitioning=Partitioning(
                strategy=Partitioning.Strategy(spec["partitioning"]["strategy"]),
                keys=spec["partitioning"].get("keys"),
                partition_count=spec["partitioning"]["partitionCount"],
            ),
            cleanup=Cleanup(
                policy=Cleanup.Policy(spec["cleanup"]["policy"]),
                retention_time_days=spec["cleanup"].get(
                    "retentionTimeDays", 1
                ),  # 1 is default Nakadi value
            ),
            schema=Schema(
                compatibility=Schema.Compatibility(spec["schema"]["compatibility"]),
                json_schema=spec["schema"]["jsonSchema"],
            ),
            auth=Auth.from_spec(spec["auth"]),
        )

    def to_spec(self) -> dict:
        return {
            "name": self.name,
            "category": str(self.category),
            "owningApplication": self.owning_application,
            "audience": str(self.audience),
            "partitioning": {
                "strategy": str(self.partitioning.strategy),
                "keys": self.partitioning.keys,
                "partitionCount": self.partitioning.partition_count,
            },
            "cleanup": {
                "policy": str(self.cleanup.policy),
                "retentionTimeDays": self.cleanup.retention_time_days,
            },
            "schema": {
                "compatibility": str(self.schema.compatibility),
                "jsonSchema": self.schema.json_schema,
            },
            "auth": self.auth.to_spec() if self.auth else {},
        }
