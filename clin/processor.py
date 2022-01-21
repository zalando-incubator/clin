import itertools
import json
import logging
from typing import Optional, Dict, Callable

from colorama import Fore
from deepdiff import DeepDiff

from clin.clients.nakadi import (
    Nakadi,
    NakadiError,
    event_type_to_payload,
    subscription_to_payload,
)
from clin.clients.nakadi_sql import NakadiSql, sql_query_to_payload
from clin.config import AppConfig
from clin.models.auth import ReadWriteAuth, ReadOnlyAuth
from clin.models.event_type import EventType
from clin.models.shared import Kind, Envelope, Entity, EventOwnerSelector
from clin.models.sql_query import SqlQuery
from clin.models.subscription import Subscription
from clin.utils import pretty_yaml, pretty_json

MODIFY_COLOR = Fore.MAGENTA
ERROR_COLOR = Fore.RED
UP_TO_DATE_COLOR = Fore.GREEN
OUTPUT_INDENTATION = 4


class Processor:
    def __init__(
        self,
        config: AppConfig,
        token: Optional[str],
        execute: bool = False,
        show_diff: bool = False,
        show_payload: bool = False,
    ):
        self.apply_func_per_kind: Dict[Kind, Callable[[str, dict], None]] = {
            Kind.EVENT_TYPE: self.apply_event_type,
            Kind.SQL_QUERY: self.apply_sql_query,
            Kind.SUBSCRIPTION: self.apply_subscription,
        }

        self.token = token
        self.config = config
        self.execute = execute
        self.show_diff = show_diff
        self.show_payload = show_payload

    def apply(self, env: str, envelope: Envelope):
        apply = self.apply_func_per_kind.get(envelope.kind, None)
        if apply is None:
            raise ProcessingError(f"Unsupported kind: {envelope.kind}")
        apply(env, envelope.spec)

    def apply_event_type(self, env: str, spec: dict):
        nakadi = self._get_nakadi(env)
        et = EventType.from_spec(spec)

        try:
            current = nakadi.get_event_type(et.name)
            if current:
                logging.debug("Found existing %s", et)
                diff = DeepDiff(current, et, ignore_order=True, report_repetition=True)
                if diff:
                    self._maybe_print_diff(et, diff)
                    self._maybe_print_payload(et)
                    self._update_event_type(nakadi, et)

                else:
                    logging.info(f"{UP_TO_DATE_COLOR}✔ Up to date:{Fore.RESET} %s", et)

            else:
                logging.debug("Not found existing %s", et)
                self._maybe_print_payload(et)
                self._create_event_type(nakadi, et)

        except NakadiError as err:
            raise ProcessingError(f"Can not process {et}: {err}") from err

    def apply_sql_query(self, env: str, spec: dict):
        nakadi = self._get_nakadi(env)
        nakadi_sql = self._get_nakadi_sql(env)
        query = SqlQuery.from_spec(spec)

        def get_changed_sections(diff: dict):
            changed_keys = itertools.chain(
                diff.get("values_changed", {}).keys(),
                diff.get("iterable_item_removed", {}).keys(),
                diff.get("iterable_item_added", {}).keys(),
                diff.get("dictionary_item_added", []),
                diff.get("dictionary_item_removed", []),
            )

            return set(k.split(".")[1] for k in changed_keys)

        try:
            current_et = nakadi.get_event_type(query.name)
            current = nakadi_sql.get_sql_query(current_et) if current_et else None
            if current:
                logging.debug("Found existing %s", query)

                diff = DeepDiff(
                    current, query, ignore_order=True, report_repetition=True
                )

                changed_sections = get_changed_sections(diff)

                if diff:
                    self._maybe_print_diff(query, diff)

                    changed_auth = "auth" in changed_sections
                    changed_sql = "sql" in changed_sections
                    forbidden_changes = changed_sections - {"auth", "sql"}

                    if forbidden_changes:
                        logging.info(
                            f"{ERROR_COLOR}× Modifying output event type is forbidden:{Fore.RESET} %s",
                            query,
                        )
                    else:
                        self._maybe_print_payload(query)
                        if changed_auth:
                            self._update_sql_query_auth(nakadi_sql, query)
                        if changed_sql:
                            self._update_sql_query_sql(nakadi_sql, query)
                else:
                    logging.info(
                        f"{UP_TO_DATE_COLOR}✔ Up to date:{Fore.RESET} %s", query
                    )

            else:
                logging.debug("Not found existing %s", query)
                self._maybe_print_payload(query)
                self._create_sql_query(nakadi, nakadi_sql, query)

        except NakadiError as err:
            raise ProcessingError(f"Can not process {query}: {err}") from err

    def apply_subscription(self, env: str, spec: dict):
        nakadi = self._get_nakadi(env)
        sub = Subscription.from_spec(spec)

        try:
            current = nakadi.get_subscription(
                sub.event_types, sub.owning_application, sub.consumer_group
            )
            if current:
                logging.debug("Found existing %s", current)
                sub.id = current.id
                diff = DeepDiff(current, sub, ignore_order=True, report_repetition=True)
                if diff:
                    self._maybe_print_diff(sub, diff)
                    self._maybe_print_payload(sub)
                    self._update_subscription(nakadi, sub)

                else:
                    logging.info(f"{UP_TO_DATE_COLOR}✔ Up to date:{Fore.RESET} %s", sub)

            else:
                logging.debug("Not found existing subscriptions matching: %s", sub)
                self._maybe_print_payload(sub)
                self._create_subscription(nakadi, sub)

        except NakadiError as err:
            raise ProcessingError(f"Can not process {sub}: {err}") from err

    def _maybe_print_diff(self, entity: Entity, diff: DeepDiff):
        def convert_to_spec(x):
            return x.to_spec()

        if self.show_diff:
            safe_diff = json.loads(
                diff.to_json(
                    default_mapping={
                        ReadOnlyAuth: convert_to_spec,
                        ReadWriteAuth: convert_to_spec,
                        EventType: convert_to_spec,
                        EventOwnerSelector: convert_to_spec,
                        SqlQuery: convert_to_spec,
                        Subscription: convert_to_spec,
                        Entity: convert_to_spec,
                    }
                )
            )

            logging.info(
                f"{MODIFY_COLOR}⦿ Found %d changes:{Fore.RESET} %s\n%s",
                len(diff),
                entity,
                pretty_yaml(safe_diff, indentation=OUTPUT_INDENTATION),
            )

    def _maybe_print_payload(self, entity: Entity):
        if self.show_payload:
            if isinstance(entity, EventType):
                payload = event_type_to_payload(entity)
            elif isinstance(entity, Subscription):
                payload = subscription_to_payload(entity)
            elif isinstance(entity, SqlQuery):
                payload = sql_query_to_payload(entity)
            else:
                logging.warning("Failed to print payload for %s", entity)
                return

            logging.info(
                f"{MODIFY_COLOR}⦿ Nakadi payload:{Fore.RESET} %s\n%s",
                entity,
                pretty_json(payload, indentation=OUTPUT_INDENTATION),
            )

    def _update_event_type(self, nakadi: Nakadi, et: EventType):
        if self.execute:
            nakadi.update_event_type(et)
            logging.info(f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s", et)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s", et)

    def _create_event_type(self, nakadi: Nakadi, et: EventType):
        if self.execute:
            nakadi.create_event_type(et)
            logging.info(f"{MODIFY_COLOR}⦿ Created:{Fore.RESET} %s", et)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will create:{Fore.RESET} %s", et)

    def _update_subscription(self, nakadi: Nakadi, sub: Subscription):
        if self.execute:
            nakadi.update_subscription(sub)
            logging.info(f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s", sub)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s", sub)

    def _create_subscription(self, nakadi: Nakadi, sub: Subscription):
        if self.execute:
            nakadi.create_subscription(sub)
            logging.info(f"{MODIFY_COLOR}⦿ Created:{Fore.RESET} %s", sub)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will create:{Fore.RESET} %s", sub)

    def _update_sql_query_auth(self, nakadi_sql: NakadiSql, query: SqlQuery):
        if self.execute:
            nakadi_sql.update_sql_query_auth(query.name, query.auth)
            logging.info(
                f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s authentication", query
            )
        else:
            logging.info(
                f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s authentication", query
            )

    def _update_sql_query_sql(self, nakadi_sql: NakadiSql, query: SqlQuery):
        if self.execute:
            nakadi_sql.update_sql_query_sql(query.name, query.sql)
            logging.info(f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s query", query)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s query", query)

    def _create_sql_query(self, nakadi: Nakadi, nakadi_sql: NakadiSql, query: SqlQuery):
        if self.execute:
            nakadi_sql.create_sql_query(query)
            logging.info(f"{MODIFY_COLOR}⦿ Created:{Fore.RESET} %s", query)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will create:{Fore.RESET} %s", query)

    def _get_nakadi(self, env: str) -> Nakadi:
        if env not in self.config.environments:
            raise ProcessingError(f"Unknown environment: {env}")
        return Nakadi(self.config.environments[env].nakadi_url, self.token)

    def _get_nakadi_sql(self, env: str) -> NakadiSql:
        if env not in self.config.environments:
            raise ProcessingError(f"Unknown environment: {env}")
        if not self.config.environments[env].nakadi_sql_url:
            raise ProcessingError("Nakadi SQL endpoint is not configured")
        return NakadiSql(self.config.environments[env].nakadi_sql_url, self.token)


class ProcessingError(Exception):
    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg
