from __future__ import annotations

import json
from typing import List, Optional

import requests
from requests import HTTPError, Response

from clin.clients.http_client import (
    HttpClient,
    rw_auth_from_payload,
    ro_auth_from_payload,
    auth_to_payload,
)
from clin.models.event_type import (
    EventType,
    EventOwnerSelector,
    Category,
    Cleanup,
    Partitioning,
    Schema,
    Audience,
)
from clin.models.subscription import Subscription
from clin.utils import MS_IN_DAY


class Nakadi(HttpClient):
    def get_event_type(self, name: str) -> Optional[EventType]:
        try:
            payload = self._get(f"event-types/{name}")
            partition_count = self.get_partition_count(name)
            return event_type_from_payload(payload, partition_count)

        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise NakadiError(
                f"Nakadi error during getting event type '{name}'", e.response
            )

    def get_partition_count(self, name: str) -> int:
        try:
            return len(self._get(f"event-types/{name}/partitions"))

        except HTTPError as e:
            raise NakadiError(
                f"Can not get partitions for event type'{name}'", e.response
            )

    def create_event_type(self, event_type: EventType):
        resp = self._post(
            "event-types", data=json.dumps(event_type_to_payload(event_type))
        )
        if resp.status_code != 201:
            raise NakadiError(
                f"Nakadi error during creation of event type '{event_type.name}'", resp
            )

    def update_event_type(self, event_type: EventType):
        resp = self._put(
            f"event-types/{event_type.name}",
            data=json.dumps(
                event_type_to_payload(event_type, include_statistics=False)
            ),
        )
        if resp.status_code != 200:
            raise NakadiError(
                f"Nakadi error during updating of event type '{event_type.name}'", resp
            )

    def get_subscription(
        self, event_types: List, owning_application: str, consumer_group: str
    ) -> Optional[Subscription]:
        params_str = Subscription.components_string(
            event_types, owning_application, consumer_group
        )

        url = f"{self._base_url}/subscriptions"
        params = {
            "event_type": ",".join(event_types),
            "owning_application": owning_application,
        }
        resp = requests.get(url, headers=self._headers, params=params)
        if resp.status_code != 200:
            raise NakadiError(
                f"Nakadi error during getting subscription for {params_str}", resp
            )

        subscriptions = [
            s for s in resp.json()["items"] if s["consumer_group"] == consumer_group
        ]
        if len(subscriptions) > 1:
            raise NakadiError(f"Got multiple subscriptions for {params_str}", resp)
        elif len(subscriptions) == 1:
            payload = subscriptions[0]
            sub = subscription_from_payload(payload)
            return sub
        else:
            return None

    def create_subscription(self, subscription: Subscription) -> Subscription:
        payload = json.dumps(subscription_to_payload(subscription))
        resp = requests.post(
            f"{self._base_url}/subscriptions", headers=self._headers, data=payload
        )
        if resp.status_code != 201:
            raise NakadiError(f"Nakadi error during creating {subscription}", resp)

        created = subscription_from_payload(resp.json())
        return created

    def update_subscription(self, subscription: Subscription):
        payload = json.dumps(subscription_to_payload(subscription))
        resp = requests.put(
            f"{self._base_url}/subscriptions/{subscription.id}",
            headers=self._headers,
            data=payload,
        )
        if resp.status_code != 204:
            raise NakadiError(f"Nakadi error during updating {subscription}", resp)


class NakadiError(Exception):
    def __init__(self, message: str, response: Response):
        self.response = response
        self._message = message

    def __str__(self):
        code = self.response.status_code
        msg = f"{self._message}: {code}"

        try:
            body = self.response.json()
            if "problem" in body:
                return msg + " - " + body["problem"]["detail"]
            else:
                return msg + " - " + body

        except Exception:
            if self.response.text:
                return msg + " - " + self.response.text
            else:
                return msg


def event_type_to_payload(
    event_type: EventType, include_statistics: bool = True
) -> dict:
    enrichment_strategies = (
        [] if event_type.category == Category.UNDEFINED else ["metadata_enrichment"]
    )
    default_statistic_part = {
        "default_statistic": {
            "messages_per_minute": 100,
            "message_size": 100,
            "read_parallelism": event_type.partitioning.partition_count,
            "write_parallelism": event_type.partitioning.partition_count,
        },
    }
    payload = {
        "name": event_type.name,
        "owning_application": event_type.owning_application,
        "category": str(event_type.category),
        "audience": str(event_type.audience),
        "partition_strategy": str(event_type.partitioning.strategy),
        "partition_key_fields": event_type.partitioning.keys,
        "cleanup_policy": event_type.cleanup.policy,
        "options": {
            "retention_time": event_type.cleanup.retention_time_days * MS_IN_DAY
        },
        "compatibility_mode": event_type.schema.compatibility,
        "schema": {
            "type": "json_schema",
            "version": "1.0.0",
            "schema": json.dumps(event_type.schema.json_schema),
        },
        "authorization": auth_to_payload(event_type.auth),
        "enrichment_strategies": enrichment_strategies,
    }
    if include_statistics:
        payload.update(default_statistic_part)
    if event_type.event_owner_selector:
        payload.update(
            {
                "event_owner_selector": {
                    "name": event_type.event_owner_selector.name,
                    "type": event_type.event_owner_selector.type,
                    "value": event_type.event_owner_selector.value,
                },
            }
        )
    return payload


def event_type_from_payload(payload: dict, partition_count: int) -> EventType:
    def maybe_event_owner_selector():
        selector = payload.get("event_owner_selector", None)
        return (
            EventOwnerSelector(
                type=EventOwnerSelector.Type(selector["type"]),
                name=selector["name"],
                value=selector["value"],
            )
            if selector
            else None
        )

    return EventType(
        name=payload["name"],
        category=Category(payload["category"]),
        owning_application=payload["owning_application"],
        audience=Audience(payload["audience"]) if "audience" in payload else None,
        partitioning=Partitioning(
            strategy=Partitioning.Strategy(payload["partition_strategy"]),
            keys=payload.get("partition_key_fields"),
            partition_count=partition_count,
        ),
        cleanup=Cleanup(
            policy=Cleanup.Policy(payload["cleanup_policy"]),
            retention_time_days=payload["options"].get("retention_time", 0)
            // MS_IN_DAY,
        ),
        schema=Schema(
            compatibility=Schema.Compatibility(payload["compatibility_mode"]),
            json_schema=json.loads(payload["schema"]["schema"]),
        ),
        auth=rw_auth_from_payload(payload["authorization"]),
        event_owner_selector=maybe_event_owner_selector(),
    )


def subscription_to_payload(subscription: Subscription) -> dict:
    return {
        "owning_application": subscription.owning_application,
        "event_types": subscription.event_types,
        "consumer_group": subscription.consumer_group,
        "initial_cursors": [],
        "read_from": "end",
        "authorization": auth_to_payload(subscription.auth),
    }


def subscription_from_payload(payload: dict) -> Subscription:
    return Subscription(
        id=payload["id"],
        owning_application=payload["owning_application"],
        event_types=payload["event_types"],
        consumer_group=payload["consumer_group"],
        auth=ro_auth_from_payload(payload["authorization"]),
    )
