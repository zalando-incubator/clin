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
        return ReadOnlyAuth(
            users=cls._parse_section(spec, "users"),
            services=cls._parse_section(spec, "services"),
        )

    def to_spec(self) -> dict[str, dict[str, list[str]]]:
        return {
            "users": {role: self.users[role] for role in self.get_roles()},
            "services": {role: self.services[role] for role in self.get_roles()},
        }

    @classmethod
    def _parse_section(cls, spec: dict, section: str) -> dict[str, list[str]]:
        def parse(role: str):
            return (
                list(set(ensure_flat_list(spec[section].get(role))))
                if spec[section]
                else []
            )

        return {role: parse(role) for role in cls.get_roles()}


@dataclass
class FullAuth(ReadOnlyAuth):
    any_token_read: bool
    any_token_write: bool

    @classmethod
    def get_roles(cls) -> list[str]:
        return ["admins", "readers", "writers"]

    @classmethod
    def from_spec(cls, spec: dict) -> FullAuth:
        return FullAuth(
            users=cls._parse_section(spec, "users"),
            services=cls._parse_section(spec, "services"),
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
