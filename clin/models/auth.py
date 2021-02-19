from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Union

from clin.utils import ensure_flat_list


@dataclass
class AllowedTenants:
    admins: List[str]
    writers: List[str]
    readers: List[str]


@dataclass
class Auth:
    users: AllowedTenants
    services: AllowedTenants
    any_token_read: bool
    any_token_write: bool

    @staticmethod
    def from_spec(
        spec: Dict[str, Dict[str, Optional[List[Union[str, List[str]]]]]]
    ) -> Auth:
        def users(role: str) -> List[str]:
            return (
                list(set(ensure_flat_list(spec["users"].get(role))))
                if spec["users"]
                else []
            )

        def services(role: str) -> List[str]:
            return (
                list(set(ensure_flat_list(spec["services"].get(role))))
                if spec["services"]
                else []
            )

        return Auth(
            users=AllowedTenants(
                admins=users("admins"),
                writers=users("writers"),
                readers=users("readers"),
            ),
            services=AllowedTenants(
                admins=services("admins"),
                writers=services("writers"),
                readers=services("readers"),
            ),
            any_token_read=spec["anyToken"].get("read", False),
            any_token_write=spec["anyToken"].get("write", False),
        )

    def to_spec(self) -> dict:
        return {
            "users": {
                "admins": self.users.admins,
                "readers": self.users.readers,
                "writers": self.users.writers,
            },
            "services": {
                "admins": self.services.admins,
                "readers": self.services.readers,
                "writers": self.services.writers,
            },
            "anyToken": {
                "read": self.any_token_read,
                "write": self.any_token_write,
            },
        }
