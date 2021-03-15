from __future__ import annotations

from dataclasses import dataclass

from clin.utils import ensure_flat_list


@dataclass
class ReadOnlyAuth:
    users: dict[str, list[str]]
    services: dict[str, list[str]]

    @classmethod
    def get_roles(cls) -> list[str]:
        return ["admins", "readers"]

    @classmethod
    def from_spec(cls, spec: dict) -> ReadOnlyAuth:
        return cls(
            users={role: cls._parse(spec, "users", role) for role in cls.get_roles()},
            services={
                role: cls._parse(spec, "services", role) for role in cls.get_roles()
            },
        )

    def to_spec(self) -> dict[str, dict[str, list[str]]]:
        return {
            "users": {role: self.users[role] for role in self.get_roles()},
            "services": {role: self.services[role] for role in self.get_roles()},
        }

    @staticmethod
    def _parse(spec: dict, key: str, role: str) -> list[str]:
        return list(set(ensure_flat_list(spec[key].get(role)))) if spec[key] else []


@dataclass
class FullAuth(ReadOnlyAuth):
    any_token_read: bool
    any_token_write: bool

    @classmethod
    def get_roles(cls) -> list[str]:
        return ["admins", "writers", "readers"]

    @classmethod
    def from_spec(cls, spec: dict) -> FullAuth:
        return FullAuth(
            users={role: cls._parse(spec, "users", role) for role in cls.get_roles()},
            services={
                role: cls._parse(spec, "services", role) for role in cls.get_roles()
            },
            any_token_read=spec["anyToken"].get("read", False),
            any_token_write=spec["anyToken"].get("write", False),
        )

    def to_spec(self) -> dict:
        return {
            **super().to_spec(),
            "anyToken": {
                "read": self.any_token_read,
                "write": self.any_token_write,
            },
        }
