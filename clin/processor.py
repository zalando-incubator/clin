import json
import logging
from typing import Union, Optional

import yaml
from colorama import Fore
from deepdiff import DeepDiff

from clin.config import AppConfig
from clin.models.auth import Auth
from clin.models.event_type import EventType
from clin.models.subscription import Subscription
from clin.nakadi import (
    Nakadi,
    NakadiError,
    event_type_to_payload,
    subscription_to_payload,
)
from clin.utils import pretty_yaml, pretty_json

MODIFY_COLOR = Fore.MAGENTA
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
        self.nakadi = {
            env: Nakadi(conf.nakadi_url, token)
            for env, conf in config.environments.items()
        }

        self.token = token
        self.execute = execute
        self.show_diff = show_diff
        self.show_payload = show_payload

    def apply(self, env: str, kind: str, spec: dict):
        if kind == "event-type":
            self.apply_event_type(env, spec)
        elif kind == "subscription":
            self.apply_subscription(env, spec)
        else:
            raise ProcessingError(f"Invalid kind: {kind}")

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

    def _get_nakadi(self, env: str):
        try:
            return self.nakadi[env]
        except KeyError:
            raise ProcessingError(f"Unknown environment: {env}")

    def _maybe_print_diff(self, entity: Union[EventType, Subscription], diff: DeepDiff):
        if self.show_diff:
            safe_diff = json.loads(
                diff.to_json(
                    default_mapping={
                        Auth: lambda x: x.to_spec(),
                        EventType: lambda x: x.to_spec(),
                    }
                )
            )

            logging.info(
                f"{MODIFY_COLOR}⦿ Found %d changes:{Fore.RESET} %s\n%s",
                len(diff),
                entity,
                pretty_yaml(safe_diff, indentation=OUTPUT_INDENTATION),
            )

    def _maybe_print_payload(self, entity: Union[EventType, Subscription]):
        if self.show_payload:
            if isinstance(entity, EventType):
                payload = event_type_to_payload(entity)
            elif isinstance(entity, Subscription):
                payload = subscription_to_payload(entity)
            else:
                logging.warning("Failed to print payload for %s", entity)
                return

            logging.info(
                f"{MODIFY_COLOR}⦿ Nakadi payload:{Fore.RESET} %s\n%s",
                entity,
                pretty_json(payload, indentation=OUTPUT_INDENTATION),
            )

    def _update_event_type(self, nakadi, et):
        if self.execute:
            nakadi.update_event_type(et)
            logging.info(f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s", et)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s", et)

    def _create_event_type(self, nakadi, et):
        if self.execute:
            nakadi.create_event_type(et)
            logging.info(f"{MODIFY_COLOR}⦿ Created:{Fore.RESET} %s", et)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will create:{Fore.RESET} %s", et)

    def _update_subscription(self, nakadi, sub):
        if self.execute:
            nakadi.update_subscription(sub)
            logging.info(f"{MODIFY_COLOR}⦿ Updated:{Fore.RESET} %s", sub)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will update:{Fore.RESET} %s", sub)

    def _create_subscription(self, nakadi, sub):
        if self.execute:
            nakadi.create_subscription(sub)
            logging.info(f"{MODIFY_COLOR}⦿ Created:{Fore.RESET} %s", sub)
        else:
            logging.info(f"{MODIFY_COLOR}⦿ Will create:{Fore.RESET} %s", sub)


class ProcessingError(Exception):
    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg
