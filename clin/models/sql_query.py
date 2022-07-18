from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from colorama import Fore

from clin.models.auth import ReadOnlyAuth
from clin.models.shared import Cleanup, Category, Entity, Kind, Audience, Partitioning


@dataclass
class OutputEventType:
    category: Category
    owning_application: str
    audience: Audience
    repartitioning: Optional[Partitioning]
    cleanup: Cleanup
    partition_compaction_key_field: str

    @staticmethod
    def from_spec(spec: dict[str, any]):
        return OutputEventType(
            category=Category(spec["category"]),
            owning_application=spec["owningApplication"],
            audience=Audience(spec["audience"]),
            repartitioning=Partitioning.from_spec(spec["repartitioning"])
            if "repartitioning" in spec
            else None,
            cleanup=Cleanup.from_spec(spec["cleanup"]),
            partition_compaction_key_field=spec["partitionCompactionKeyField"],
        )

    def to_spec(self) -> dict[str, any]:
        spec = {
            "category": str(self.category),
            "owningApplication": self.owning_application,
            "audience": str(self.audience),
            "cleanup": self.cleanup.to_spec(),
            "partitionCompactionKeyField": self.partition_compaction_key_field,
        }

        if self.repartitioning:
            spec["repartitioning"] = self.repartitioning.to_spec()

        return spec


@dataclass
class SqlQuery(Entity):
    name: str
    sql: str
    envelope: bool
    output_event_type: OutputEventType
    auth: ReadOnlyAuth

    def __str__(self) -> str:
        return f"sql query {Fore.BLUE}{self.name}{Fore.RESET}"

    @property
    def kind(self) -> Kind:
        return Kind.SQL_QUERY

    @staticmethod
    def from_spec(spec: dict[str, any]) -> SqlQuery:
        return SqlQuery(
            name=spec["name"],
            sql=spec["sql"],
            envelope=spec["envelope"],
            output_event_type=OutputEventType.from_spec(spec["outputEventType"]),
            auth=ReadOnlyAuth.from_spec(spec["auth"]),
        )

    def to_spec(self) -> dict[str, any]:
        return {
            "name": self.name,
            "sql": self.sql,
            "envelope": self.envelope,
            "outputEventType": self.output_event_type.to_spec(),
            "auth": self.auth.to_spec() if self.auth else {},
        }
