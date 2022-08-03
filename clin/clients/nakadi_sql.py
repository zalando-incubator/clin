import json
from typing import Optional

from requests import HTTPError

from clin.clients.nakadi import NakadiError
from clin.clients.http_client import HttpClient, ro_auth_from_payload, auth_to_payload
from clin.models.auth import Auth
from clin.models.event_type import EventType
from clin.models.sql_query import SqlQuery, OutputEventType
from clin.models.shared import Category, Cleanup, Audience, Partitioning
from clin.utils import MS_IN_DAY


class NakadiSql(HttpClient):
    def get_sql_query(self, event_type: EventType) -> Optional[SqlQuery]:
        try:
            payload = self._get(f"queries/{event_type.name}")
            return sql_query_from_payload(event_type, payload)

        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise NakadiError(
                f"Nakadi error trying to get sql query '{event_type}'", e.response
            )

    def create_sql_query(self, sql_query: SqlQuery):
        resp = self._post("queries", data=json.dumps(sql_query_to_payload(sql_query)))
        if resp.status_code != 201:
            raise NakadiError(
                f"Nakadi error during creation of sql query '{sql_query.name}'", resp
            )

    def update_sql_query_auth(self, query_name: str, auth: Auth):
        resp = self._put(
            f"queries/{query_name}/authorization",
            data=json.dumps(auth_to_payload(auth)),
        )
        if resp.status_code != 200:
            raise NakadiError(
                f"Nakadi error during updating of sql query '{query_name}'", resp
            )

    def update_sql_query_sql(self, query_name: str, sql: str):
        resp = self._put(f"queries/{query_name}/sql", data=json.dumps({"sql": sql}))
        if resp.status_code != 204:
            raise NakadiError(
                f"Nakadi error during updating of sql query '{query_name}'", resp
            )


def output_event_type_from_payload(
    event_type: EventType, payload: dict
) -> OutputEventType:
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
        owning_application=payload.get(
            "owning_application", event_type.owning_application
        ),
        audience=Audience(payload["audience"])
        if "audience" in payload
        else event_type.audience,
        repartitioning=convert_repartitioning(),
        cleanup=Cleanup(
            policy=Cleanup.Policy(payload["cleanup_policy"]),
            retention_time_days=payload.get("retention_time", 0) // MS_IN_DAY,
        ),
        partition_compaction_key_field=payload.get("partition_compaction_key_field"),
    )


def sql_query_from_payload(event_type: EventType, payload: dict) -> SqlQuery:
    if payload["id"] != payload["output_event_type"]["name"]:
        raise NakadiError(
            "The output event type's name does not match the sql query id."
            " This is unexpected and unsupported - please report this issue in the clin project on GitHub!"
        )

    return SqlQuery(
        name=payload["id"],
        sql=payload["sql"],
        envelope=payload["envelope"],
        output_event_type=output_event_type_from_payload(
            event_type, payload["output_event_type"]
        ),
        auth=ro_auth_from_payload(payload["authorization"]),
        read_from=payload["read_from"],
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
        payload["output_event_type"]["repartition_parameters"] = {
            "number_of_partitions": sql_query.output_event_type.repartitioning.partition_count,
            "partition_strategy": str(
                sql_query.output_event_type.repartitioning.strategy
            ),
            "partition_key_fields": sql_query.output_event_type.repartitioning.keys,
        }

    if sql_query.output_event_type.partition_compaction_key_field:
        payload["output_event_type"][
            "partition_compaction_key_field"
        ] = sql_query.output_event_type.partition_compaction_key_field

    if sql_query.read_from:
        payload["read_from"] = sql_query.read_from

    return payload
