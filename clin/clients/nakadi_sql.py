from typing import Optional

from requests import HTTPError

from clin.clients.nakadi import NakadiError
from clin.clients.shared import HttpClient, auth_to_payload, auth_from_payload
from clin.models.sql_query import SqlQuery, OutputEventType
from clin.models.shared import Category, Cleanup, Audience, Partitioning
from clin.utils import MS_IN_DAY


class NakadiSql(HttpClient):
    def get_sql_query(self, name: str) -> Optional[SqlQuery]:
        try:
            payload = self._get(f"queries/{name}")
            return sql_query_from_payload(payload)

        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise NakadiError(
                f"Nakadi error trying to get sql query '{name}'", e.response
            )


def output_event_type_from_payload(payload: dict) -> OutputEventType:
    def convert_repartitioning() -> Optional[Partitioning]:
        return (
            Partitioning(
                strategy=Partitioning.Strategy(
                    payload["repartition_parameters"]["partition_strategy"]
                ),
                keys=payload["repartition_parameters"].get("partition_key_fields"),
                partition_count=int(
                    payload["repartition_parameters"]["number_of_partitions"]
                ),
            )
            if "repartition_parameters" in payload
            else None
        )

    return OutputEventType(
        category=Category(payload["category"]),
        owning_application=payload.get("owning_application", None),
        audience=Audience(payload["audience"]) if "audience" in payload else None,
        repartitioning=convert_repartitioning(),
        cleanup=Cleanup(
            policy=Cleanup.Policy(payload["cleanup_policy"]),
            retention_time_days=payload.get("retention_time", 0) // MS_IN_DAY,
        ),
    )


def sql_query_from_payload(payload: dict) -> SqlQuery:
    if payload["id"] != payload["output_event_type"]["name"]:
        raise NakadiError(
            "The output event type's name does not match the sql query id."
            " This is unexpected and unsupported - please report this issue in the clin project on GitHub!"
        )

    return SqlQuery(
        name=payload["id"],
        sql=payload["sql"],
        envelope=payload["envelope"],
        output_event_type=output_event_type_from_payload(payload["output_event_type"]),
        auth=auth_from_payload(payload["authorization"]),
    )


def sql_query_to_payload(sql_query: SqlQuery) -> dict:
    payload = {
        "id": sql_query.name,
        "sql": sql_query.sql,
        "envelope": sql_query.envelope,
        "output_event_type": {
            "name": sql_query.name,
            "owning_application": sql_query.output_event_type.owning_application,
            "category": str(sql_query.output_event_type.category),
            "audience": str(sql_query.output_event_type.audience),
            "cleanup_policy": str(sql_query.output_event_type.cleanup.policy),
            "retention_time": sql_query.output_event_type.cleanup.retention_time_days
            * MS_IN_DAY,
        },
        "authorization": auth_to_payload(sql_query.auth),
    }

    if sql_query.output_event_type.repartitioning:
        payload["repartition_parameters"] = {
            "number_of_partitions": sql_query.output_event_type.repartitioning.partition_count,
            "partition_strategy": str(
                sql_query.output_event_type.repartitioning.strategy
            ),
            "partition_key_fields": sql_query.output_event_type.repartitioning.keys,
        }

    return payload
