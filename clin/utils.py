import json
import logging
import sys

import yaml
from pygments import highlight
from pygments.formatter import Formatter
from pygments.formatters.other import NullFormatter
from pygments.formatters.terminal256 import TerminalTrueColorFormatter
from pygments.lexers.data import JsonLexer, YamlLexer

MS_IN_DAY = 24 * 60 * 60 * 1000


def walk(src, f):
    if isinstance(src, dict):
        for k, v in src.items():
            src[k] = walk(v, f)
        return src
    elif isinstance(src, list):
        for i, e in enumerate(src):
            src[i] = walk(e, f)
        return src
    else:
        return f(src)  # walk(f(src, f)) to enable recursive resolutions


def ensure_flat_list(val) -> list:
    if val is None:
        return []
    elif isinstance(val, list):
        return [item for sublist in val for item in ensure_flat_list(sublist)]
    else:
        return [val]


def configure_logging(verbose: bool):
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def pretty_yaml(val: dict, indentation: int = 0) -> str:
    raw = highlight(
        yaml.dump(val, sort_keys=False), YamlLexer(), _get_formatter()
    ).strip()
    return _indent(raw, indentation)


def pretty_json(val: dict, indentation: int = 0) -> str:
    raw = highlight(
        json.dumps(val, indent=2, sort_keys=False), JsonLexer(), _get_formatter()
    ).strip()
    return _indent(raw, indentation)


def _indent(s: str, indentation: int) -> str:
    prepend = " " * indentation
    return "\n".join(prepend + l for l in s.splitlines())


def _get_formatter() -> Formatter:
    return TerminalTrueColorFormatter() if sys.stdout.isatty() else NullFormatter()
