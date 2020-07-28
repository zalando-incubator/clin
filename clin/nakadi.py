from __future__ import annotations

import json
from typing import List, Optional

import requests

from clin.models.auth import Auth, AllowedTenants
from clin.models.event_type import (
    EventType,
    Category,
    Cleanup,
    Partitioning,
    Schema,
    Audience,
)
from clin.models.subscription import Subscription
from clin.utils import MS_IN_DAY


class Nakadi:
    def __init__(self, base_url: str, token: Optional[str]):
        self._base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json", "User-Agent": "clin"}

        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def get_event_type(self, name: str) -> Optional[EventType]:
        url = f"{self._base_url}/event-types/{name}"
        resp = requests.get(url, headers=self._headers)
        if resp.status_code == 200:
            payload = resp.json()
            partition_count = self.get_partition_count(name)
            return event_type_from_payload(payload, partition_count)
        elif resp.status_code == 404:
            return None
        else:
            raise NakadiError(f"Nakadi error during getting event type '{name}'", resp)

    def get_partition_count(self, name: str) -> int:
        url = f"{self._base_url}/event-types/{name}/partitions"
        resp = requests.get(url, headers=self._headers)
        cursors = []
        if resp.status_code == 200:
            cursors = resp.json()
        if not cursors:
            raise NakadiError(f"Can not get partitions for event type'{name}'", resp)
        return len(cursors)

    def create_event_type(self, event_type: EventType):
        payload = json.dumps(event_type_to_payload(event_type))
        resp = requests.post(
            f"{self._base_url}/event-types", headers=self._headers, data=payload
        )
        if resp.status_code != 201:
            raise NakadiError(
                f"Nakadi error during creation of event type '{event_type.name}'", resp
            )

    def update_event_type(self, event_type: EventType):
        payload = json.dumps(event_type_to_payload(event_type))
        resp = requests.put(
            f"{self._base_url}/event-types/{event_type.name}",
            headers=self._headers,
            data=payload,
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
    def __init__(self, message: str, response: requests.Response):
        self.response = response
        self._message = message

    def __str__(self):
        code = self.response.status_code
        msg = f"{self._message}: {code}"
        if code // 100 == 2:
            msg += f" - {self.response.json()}"
        elif code // 100 >= 4:
            problem = self.response.json()
            msg += f" - {problem['detail']}"
        else:
            msg += ": " + self.response.text
        return msg


def _auth_to_payload(a: Auth) -> dict:
    any_token_write = [{"data_type": "*", "value": "*"}] if a.any_token_write else []
    any_token_read = [{"data_type": "*", "value": "*"}] if a.any_token_read else []
    return {
        "admins": [{"data_type": "user", "value": user} for user in a.users.admins]
        + [{"data_type": "service", "value": service} for service in a.services.admins],
        "writers": [{"data_type": "user", "value": user} for user in a.users.writers]
        + [{"data_type": "service", "value": service} for service in a.services.writers]
        + any_token_write,
        "readers": [{"data_type": "user", "value": user} for user in a.users.readers]
        + [{"data_type": "service", "value": service} for service in a.services.readers]
        + any_token_read,
    }


def _auth_from_payload(payload: dict) -> Optional[Auth]:
    if not payload:
        return None

    auth = Auth(AllowedTenants([], [], []), AllowedTenants([], [], []), False, False)
    for admin in payload.get("admins", []):
        if admin["data_type"] == "user":
            auth.users.admins.append(admin["value"])
        if admin["data_type"] == "service":
            auth.services.admins.append(admin["value"])
    for writer in payload.get("writers", []):
        if writer["data_type"] == "user":
            auth.users.writers.append(writer["value"])
        if writer["data_type"] == "service":
            auth.services.writers.append(writer["value"])
        if writer["data_type"] == "*":
            auth.any_token_write = True
    for reader in payload.get("readers", []):
        if reader["data_type"] == "user":
            auth.users.readers.append(reader["value"])
        if reader["data_type"] == "service":
            auth.services.readers.append(reader["value"])
        if reader["data_type"] == "*":
            auth.any_token_read = True

    return auth


def event_type_to_payload(event_type: EventType) -> dict:
    enrichment_strategies = (
        [] if event_type.category == Category.UNDEFINED else ["metadata_enrichment"]
    )
    return {
        "name": event_type.name,
        "owning_application": event_type.owning_application,
        "category": event_type.category,
        "audience": event_type.audience,
        "partition_strategy": event_type.partitioning.strategy,
        "partition_key_fields": event_type.partitioning.keys,
        "default_statistic": {
            "messages_per_minute": 100,
            "message_size": 100,
            "read_parallelism": event_type.partitioning.partition_count,
            "write_parallelism": event_type.partitioning.partition_count,
        },
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
        "authorization": _auth_to_payload(event_type.auth),
        "enrichment_strategies": enrichment_strategies,
    }


def event_type_from_payload(payload: dict, partition_count: int) -> EventType:
    return EventType(
        name=payload["name"],
        category=Category(payload["category"]),
        owning_application=payload["owning_application"],
        audience=Audience(payload["audience"]) if payload.get("audience") else None,
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
        auth=_auth_from_payload(payload["authorization"]),
    )


def subscription_to_payload(subscription: Subscription) -> dict:
    return {
        "owning_application": subscription.owning_application,
        "event_types": subscription.event_types,
        "consumer_group": subscription.consumer_group,
        "initial_cursors": [],
        "read_from": "end",
        "authorization": _auth_to_payload(subscription.auth),
    }


def subscription_from_payload(payload: dict) -> Subscription:
    return Subscription(
        id=payload["id"],
        owning_application=payload["owning_application"],
        event_types=payload["event_types"],
        consumer_group=payload["consumer_group"],
        auth=_auth_from_payload(payload["authorization"]),
    )
