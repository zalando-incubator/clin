import os
from typing import Optional

import requests
from requests import Response

from clin import __version__
from clin.models.auth import Auth, AllowedTenants


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
        resp = requests.get(url, headers=self._headers, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, **kwargs) -> Response:
        url = os.path.join(self._base_url, path)
        return requests.post(url, **kwargs)

    def _put(self, path: str, **kwargs) -> Response:
        url = os.path.join(self._base_url, path)
        return requests.put(url, **kwargs)


def auth_to_payload(a: Auth) -> dict:
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


def auth_from_payload(payload: dict) -> Optional[Auth]:
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
