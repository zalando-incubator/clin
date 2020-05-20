#!/usr/bin/env python3
import logging
import os
from pathlib import Path
from typing import Optional

import click

from clin.clinfile import calculate_scope
from clin.config import ConfigurationError, load_config
from clin.nakadi import Nakadi, NakadiError
from clin.processor import Processor, ProcessingError
from clin.utils import configure_logging, pretty_yaml, pretty_json
from clin.yamlops import YamlLoader, load_manifest, load_yaml, YamlError

DEFAULT_YAML_LOADER = YamlLoader()


@click.group()
def cli():
    """Manage Nakadi resources"""

    pass


@cli.command("apply")
@click.option("-e", "--env", required=True, type=str, help="Nakadi environment")
@click.option("-t", "--token", required=False, type=str, help="Bearer token")
@click.option(
    "-X",
    "--execute",
    is_flag=True,
    default=False,
    help="Execute updates (default - false)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.option(
    "-d", "--show-diff", is_flag=True, default=False, help="Show diff (default - false)"
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
    env: str,
    token: Optional[str],
    execute: bool,
    verbose: bool,
    show_diff: bool,
    show_payload: bool,
    file: str,
):
    """Create or update Nakadi resource from single yaml manifest file\n
     Values to fill {{VARIABLES}} are taken from system environment"""
    configure_logging(verbose)

    try:
        config = load_config()
        kind, spec = load_manifest(Path(file), DEFAULT_YAML_LOADER, os.environ)
        processor = Processor(config, token, execute, show_diff, show_payload)
        processor.apply(env, kind, spec)

    except (ProcessingError, NakadiError, ConfigurationError, YamlError) as ex:
        logging.error(ex)
        exit(-1)

    except Exception as ex:
        logging.exception(ex)
        exit(-1)


@cli.command("process")
@click.option("-t", "--token", required=False, type=str, help="Bearer token")
@click.option("-X", "--execute", is_flag=True, default=False, help="Execute updates")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.option(
    "-d", "--show-diff", is_flag=True, default=False, help="Show diff (default - false)"
)
@click.option(
    "-p",
    "--show-payload",
    is_flag=True,
    default=False,
    help="Show Nakadi payload (default - false)",
)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, readable=True))
def process(
    token: Optional[str],
    execute: bool,
    verbose: bool,
    show_diff: bool,
    show_payload: bool,
    file: str,
):
    """Create or update multiple Nakadi resources from clin file"""
    configure_logging(verbose)

    try:
        config = load_config()
        processor = Processor(config, token, execute, show_diff, show_payload)
        file_path: Path = Path(file)
        master = load_yaml(file_path, DEFAULT_YAML_LOADER, os.environ)
        scope = calculate_scope(master, file_path.parent, DEFAULT_YAML_LOADER)
        event_types = [et for et in scope if et.kind == "event-type"]
        subscriptions = [sub for sub in scope if sub.kind == "subscription"]

        for task in event_types + subscriptions:
            logging.debug(
                "[%s] applying file %s to %s environment",
                task.id,
                task.path,
                task.target,
            )
            processor.apply(task.target, task.kind, task.spec)

    except (ProcessingError, ConfigurationError, YamlError) as ex:
        logging.error(ex)
        exit(-1)

    except Exception as ex:
        logging.exception(ex)
        exit(-1)


@cli.command("dump")
@click.option("-e", "--env", required=True, type=str, help="Nakadi environment")
@click.option("-t", "--token", required=False, type=str, help="Bearer token")
@click.option(
    "-o",
    "--output",
    default="yaml",
    type=click.Choice(["yaml", "json"]),
    help="Output format",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Verbose output (default - false)",
)
@click.argument("event_type", type=str)
def dump(env: str, token: Optional[str], output: str, verbose: bool, event_type: str):
    """Print manifest of existing Nakadi event type"""
    configure_logging(verbose)

    try:
        config = load_config()
        if env not in config.environments:
            logging.error(f"Environment not found in configuration: {env}")
            exit(-1)

        nakadi = Nakadi(config.environments[env].nakadi_url, token)
        et = nakadi.get_event_type(event_type)
        if not et:
            logging.error("Event type not found in Nakadi %s: %s", env, event_type)
            exit(-1)

        if output.lower() == "yaml":
            logging.info(pretty_yaml(et.to_spec()))
        elif output.lower() == "json":
            logging.info(pretty_json(et.to_spec()))
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
