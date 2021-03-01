from typing import Optional

from requests import HTTPError

from clin.clients.nakadi import NakadiError
from clin.clients.shared import HttpClient, auth_to_payload, auth_from_payload
from clin.models.sql_query import SqlQuery, OutputEventType
from clin.models.shared import Category, Cleanup
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
        output_event_type=OutputEventType(
            category=Category(payload["output_event_type"]["category"]),
            cleanup=Cleanup(
                policy=Cleanup.Policy(payload["output_event_type"]["cleanup_policy"]),
                retention_time_days=payload["output_event_type"].get(
                    "retention_time", 0
                )
                // MS_IN_DAY,
            ),
        ),
        auth=auth_from_payload(payload["authorization"]),
    )


def sql_query_to_payload(sql_query: SqlQuery) -> dict:
    return {
        "id": sql_query.name,
        "sql": sql_query.sql,
        "envelope": sql_query.envelope,
        "output_event_type": {
            "name": sql_query.name,
            "category": str(sql_query.output_event_type.category),
            "cleanup_policy": str(sql_query.output_event_type.cleanup.policy),
            "retention_time": sql_query.output_event_type.cleanup.retention_time_days
            * MS_IN_DAY,
        },
        "authorization": auth_to_payload(sql_query.auth),
    }
