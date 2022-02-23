from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from clin.utils import ensure_flat_list


@dataclass
class Auth(ABC):
    users: dict[str, list[str]]
    teams: dict[str, list[str]]
    services: dict[str, list[str]]
    any_token: dict[str, bool]

    @classmethod
    @abstractmethod
    def get_roles(cls) -> list[str]:
        pass

    @classmethod
    @abstractmethod
    def get_any_token_values(cls) -> list[str]:
        pass

    @classmethod
    def from_spec(cls, spec: dict) -> Auth:
        return cls(
            users=cls._parse_section(spec, "users"),
            teams=cls._parse_section(spec, "teams"),
            services=cls._parse_section(spec, "services"),
            any_token=cls._parse_any_token(spec),
        )

    def to_spec(self) -> dict[str, dict[str, list[str]]]:
        return {
            "users": {role: self.users[role] for role in self.get_roles()},
            "teams": {role: self.teams[role] for role in self.get_roles()},
            "services": {role: self.services[role] for role in self.get_roles()},
            "anyToken": {
                role: self.any_token.get(role, False)
                for role in self.get_any_token_values()
            },
        }

    @classmethod
    def _parse_section(cls, spec: dict, section: str) -> dict[str, list[str]]:
        def parse(role: str):
            return (
                list(set(ensure_flat_list(spec[section].get(role))))
                if section in spec and spec[section]
                else []
            )

        return {role: parse(role) for role in cls.get_roles()}

    @classmethod
    def _parse_any_token(cls, spec: dict) -> dict[str, bool]:
        return {
            role: spec.get("anyToken", {}).get(role, False)
            for role in cls.get_any_token_values()
        }


@dataclass
class ReadOnlyAuth(Auth):
    @classmethod
    def get_roles(cls) -> list[str]:
        return ["admins", "readers"]

    @classmethod
    def get_any_token_values(cls) -> list[str]:
        return ["read"]


@dataclass
class ReadWriteAuth(Auth):
    @classmethod
    def get_roles(cls) -> list[str]:
        return ["admins", "readers", "writers"]

    @classmethod
    def get_any_token_values(cls) -> list[str]:
        return ["read", "write"]
