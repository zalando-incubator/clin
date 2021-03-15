import os
from typing import Optional

import requests
from requests import Response

from clin import __version__


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
        return requests.post(url, headers=self._headers, **kwargs)

    def _put(self, path: str, **kwargs) -> Response:
        url = os.path.join(self._base_url, path)
        return requests.put(url, headers=self._headers, **kwargs)
