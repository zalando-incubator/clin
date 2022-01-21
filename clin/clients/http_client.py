import logging
import os
from typing import Optional, TypeVar

import requests
from requests import Response

from clin import __version__
from clin.models.auth import Auth, ReadOnlyAuth, ReadWriteAuth

TAuth = TypeVar("TAuth", bound=Auth)


class HttpClient:
    def __init__(self, base_url: str, token: Optional[str]):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "User-Agent": f"clin+{__version__}",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, **kwargs) -> dict:
        url = os.path.join(self._base_url, path)
        logging.debug(f"GET {url}")
        resp = requests.get(url, headers=self._headers, **kwargs)
        logging.debug(f"-> response code {resp.status_code}")
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, **kwargs) -> Response:
        url = os.path.join(self._base_url, path)
        logging.debug(f"POST {url}")
        resp = requests.post(url, headers=self._headers, **kwargs)
        logging.debug(f"-> response code {resp.status_code}")
        return resp

    def _put(self, path: str, **kwargs) -> Response:
        url = os.path.join(self._base_url, path)
        logging.debug(f"PUT {url}")
        resp = requests.put(url, headers=self._headers, **kwargs)
        logging.debug(f"-> response code {resp.status_code}")
        return resp


def auth_to_payload(auth: Auth) -> dict:
    def parse(role: str):
        def el(key: str):
            return [
                {"data_type": key, "value": x} for x in getattr(auth, key + "s")[role]
            ]

        return el("user") + el("service") + el("team")

    payload = {role: parse(role) for role in auth.get_roles()}
    if auth.any_token.get("read", False):
        payload["readers"].append({"data_type": "*", "value": "*"})
    if auth.any_token.get("write", False):
        payload["writers"].append({"data_type": "*", "value": "*"})

    return payload


def ro_auth_from_payload(payload: dict) -> Optional[ReadOnlyAuth]:
    return _auth_from_payload(ReadOnlyAuth({}, {}, {}, {"read": False}), payload)


def rw_auth_from_payload(payload: dict) -> Optional[ReadWriteAuth]:
    return _auth_from_payload(
        ReadWriteAuth({}, {}, {}, {"read": False, "write": False}), payload
    )


def _auth_from_payload(auth: TAuth, payload: dict) -> Optional[TAuth]:
    if not payload:
        return None

    for role in auth.get_roles():  # admins, readers
        auth.teams[role] = []
        auth.users[role] = []
        auth.services[role] = []
        for el in payload.get(role, []):
            if el["data_type"] == "team":
                auth.teams[role].append(el["value"])
            if el["data_type"] == "user":
                auth.users[role].append(el["value"])
            if el["data_type"] == "service":
                auth.services[role].append(el["value"])
            if el["data_type"] == "*":
                if role == "readers" and "read" in auth.get_any_token_values():
                    auth.any_token["read"] = True
                if role == "writers" and "write" in auth.get_any_token_values():
                    auth.any_token["write"] = True

    return auth
