from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class EnvironmentConfig:
    nakadi_url: str
    nakadi_sql_url: Optional[str]

    @staticmethod
    def load(name: str, content: dict[str, str]) -> EnvironmentConfig:
        if "nakadi_url" not in content:
            raise ConfigurationError(
                f"Nakadi url not found in configuration for environment: {name}"
            )

        return EnvironmentConfig(
            nakadi_url=content["nakadi_url"],
            nakadi_sql_url=content.get("nakadi_sql_url", None),
        )


@dataclass
class AppConfig:
    environments: dict[str, EnvironmentConfig]

    @staticmethod
    def load(content: dict) -> AppConfig:
        if "environments" not in content:
            raise ConfigurationError(f"Environments section not found in configuration")

        return AppConfig(
            {
                name: EnvironmentConfig.load(name, val)
                for name, val in content["environments"].items()
            }
        )


def load_config() -> AppConfig:
    config_locations = [Path.cwd(), Path.home()]

    for file_name in [str(path / ".clin") for path in config_locations]:
        if os.path.isfile(file_name):
            try:
                with open(file_name) as f:
                    content = yaml.safe_load(f)
            except Exception as ex:
                raise ConfigurationError(
                    f"Failed to parse configuration file: {file_name}: {str(ex)}"
                )

            return AppConfig.load(content)

    raise ConfigurationError(
        f"No valid configuration file found. Inspected locations: "
        f"{[str(path) for path in config_locations]}"
    )


class ConfigurationError(Exception):
    def __init__(self, message: str):
        self.message = message
