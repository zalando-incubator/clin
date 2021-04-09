#!/usr/bin/env python3
import logging
import os
from pathlib import Path
from typing import Tuple, Optional

import click

from clin import __version__
from clin.clients.nakadi_sql import NakadiSql
from clin.clinfile import calculate_scope
from clin.config import ConfigurationError, load_config
from clin.clients.nakadi import Nakadi, NakadiError
from clin.models.shared import Kind
from clin.processor import Processor, ProcessingError
from clin.utils import configure_logging, pretty_yaml, pretty_json
from clin.yamlops import YamlLoader, load_manifest, load_yaml, YamlError

DEFAULT_YAML_LOADER = YamlLoader()


@click.group()
@click.version_option(version=__version__)
def cli():
    """Manage Nakadi resources"""
    pass


@cli.command("apply")
@click.option(
    "-t",
    "--token",
    required=False,
    type=str,
    help="The bearer token to authenticate the Nakadi requests",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.option(
    "-e",
    "--env",
    required=True,
    type=str,
    help="The Nakadi environment to target",
)
@click.option(
    "-X",
    "--execute",
    is_flag=True,
    default=False,
    help="Execute updates (default - false)",
)
@click.option(
    "-d",
    "--show-diff",
    is_flag=True,
    default=False,
    help="Display the schema diff (default - false)",
)
@click.option(
    "-p",
    "--show-payload",
    is_flag=True,
    default=False,
    help="Show Nakadi payload (default - false)",
)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, readable=True))
def apply(
    token: Optional[str],
    verbose: bool,
    env: str,
    execute: bool,
    show_diff: bool,
    show_payload: bool,
    file: str,
):
    """Create or update Nakadi resource from single yaml manifest file\n
    Values to fill {{VARIABLES}} are taken from system environment"""
    configure_logging(verbose)

    try:
        config = load_config()
        envelope = load_manifest(Path(file), DEFAULT_YAML_LOADER, os.environ)
        processor = Processor(config, token, execute, show_diff, show_payload)
        processor.apply(env, envelope)

    except (ProcessingError, NakadiError, ConfigurationError, YamlError) as ex:
        logging.error(ex)
        exit(-1)

    except Exception as ex:
        logging.exception(ex)
        exit(-1)


@cli.command("process")
@click.option(
    "-t",
    "--token",
    required=False,
    type=str,
    help="The bearer token to authenticate the Nakadi requests",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.option(
    "-X",
    "--execute",
    is_flag=True,
    default=False,
    help="Execute the updates (default - false)",
)
@click.option(
    "-d",
    "--show-diff",
    is_flag=True,
    default=False,
    help="Display the schema diff (default - false)",
)
@click.option(
    "-p",
    "--show-payload",
    is_flag=True,
    default=False,
    help="Show Nakadi payload (default - false)",
)
@click.option(
    "-i",
    "--id",
    required=False,
    type=str,
    multiple=True,
    help="Select one or multiple steps to process by their id",
)
@click.option(
    "-e",
    "--env",
    required=False,
    type=str,
    multiple=True,
    help="Select one or multiple steps to process by matching the target environment",
)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, readable=True))
def process(
    token: Optional[str],
    verbose: bool,
    execute: bool,
    show_diff: bool,
    show_payload: bool,
    id: Tuple[str],
    env: Tuple[str],
    file: str,
):
    """Create or update multiple Nakadi resources from a clin file"""
    configure_logging(verbose)

    try:
        config = load_config()
        processor = Processor(config, token, execute, show_diff, show_payload)
        file_path: Path = Path(file)
        master = load_yaml(file_path, DEFAULT_YAML_LOADER, os.environ)

        scope = calculate_scope(master, file_path.parent, DEFAULT_YAML_LOADER, id, env)

        for task in (
            scope[Kind.EVENT_TYPE] + scope[Kind.SQL_QUERY] + scope[Kind.SUBSCRIPTION]
        ):
            logging.debug(
                "[%s] applying file %s to %s environment",
                task.id,
                task.path,
                task.target,
            )
            processor.apply(task.target, task.envelope)

    except (ProcessingError, ConfigurationError, YamlError) as ex:
        logging.error(ex)
        exit(-1)

    except Exception as ex:
        logging.exception(ex)
        exit(-1)


@cli.command("dump")
@click.option(
    "-t",
    "--token",
    required=False,
    type=str,
    help="The bearer token to authenticate the Nakadi requests",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.option(
    "--include-envelope",
    is_flag=True,
    default=False,
    help="Add clin envelope to schema (default - false)",
)
@click.option(
    "-e",
    "--env",
    required=True,
    type=str,
    help="The Nakadi environment to target",
)
@click.option(
    "-o",
    "--output",
    default="yaml",
    type=click.Choice(["yaml", "json"]),
    help="The output format (default - yaml)",
)
@click.argument("event_type", type=str)
def dump(
    token: Optional[str],
    verbose: bool,
    env: str,
    output: str,
    include_envelope: bool,
    event_type: str,
):
    """Print manifest of existing Nakadi event type"""
    configure_logging(verbose)

    try:
        config = load_config()
        if env not in config.environments:
            logging.error(f"Environment not found in configuration: {env}")
            exit(-1)

        nakadi = Nakadi(config.environments[env].nakadi_url, token)
        entity = nakadi.get_event_type(event_type)

        if entity and config.environments[env].nakadi_sql_url:
            nakadi_sql = NakadiSql(config.environments[env].nakadi_sql_url, token)
            entity = nakadi_sql.get_sql_query(entity) or entity

        if entity is None:
            logging.error("Event type not found in Nakadi %s: %s", env, event_type)
            exit(-1)

        payload = (
            entity.to_envelope().to_manifest() if include_envelope else entity.to_spec()
        )

        if output.lower() == "yaml":
            logging.info(pretty_yaml(payload))
        elif output.lower() == "json":
            logging.info(pretty_json(payload))
        else:
            logging.error("Invalid output format: %s", output)
            exit(-1)

    except (NakadiError, ConfigurationError) as ex:
        logging.error(ex)
        exit(-1)

    except Exception as ex:
        logging.exception(ex)
        exit(-1)


if __name__ == "__main__":
    cli()
