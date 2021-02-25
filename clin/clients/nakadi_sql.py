from typing import Optional

from requests import HTTPError

from clin.clients.nakadi import NakadiError
from clin.clients.shared import HttpClient, auth_to_payload, auth_from_payload
from clin.models.auth import Auth
from clin.models.projection import Projection, OutputEventType
from clin.models.shared import Category, Cleanup
from clin.utils import MS_IN_DAY


class NakadiSql(HttpClient):
    def get_projection(self, id: str) -> Optional[Projection]:
        try:
            payload = self._get(f"queries/{id}")
            return projection_from_payload(payload)

        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise NakadiError(
                f"Nakadi error trying to get projection '{id}'", e.response
            )


def projection_from_payload(payload: dict) -> Projection:
    if payload["id"] != payload["output_event_type"]["name"]:
        raise NakadiError(
            "The output event type's name does not match the projection id."
            " This is unexpected and unsupported - please report this issue in the clin project on GitHub!"
        )

    return Projection(
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


def projection_to_payload(projection: Projection) -> dict:
    return {
        "id": projection.name,
        "sql": projection.sql,
        "envelope": projection.envelope,
        "output_event_type": {
            "name": projection.name,
            "category": str(projection.output_event_type.category),
            "cleanup_policy": str(projection.output_event_type.cleanup.policy),
            "retention_time": projection.output_event_type.cleanup.retention_time_days
            * MS_IN_DAY,
        },
        "authorization": auth_to_payload(projection.auth),
    }
