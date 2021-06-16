import logging
import re
from pathlib import Path
from typing import List

import yaml

from clin.models.shared import Envelope
from clin.utils import walk


class YamlLoader:
    def __init__(self, **kwargs):
        self._include_marker = kwargs.get("include_marker", "@@@")
        self._include_substitution = kwargs.get("include_substitution", "📁")
        self._variable_markers = kwargs.get("variable_markers", ("{{", "}}"))
        self._variable_substitutions = kwargs.get("variable_substitutions", ("👉", "👈"))

    def load_yaml_from_file(self, path: Path, env: dict) -> dict:
        yml = self._load_yaml_from_file(path, env, [])
        yml = self._resolve_variables(yml, env, path)
        return yml

    def _load_yaml_from_file(self, path: Path, env: dict, visited: List[Path]) -> dict:
        def resolve_include(src):
            if not isinstance(src, str) or not src.startswith(
                self._include_substitution
            ):
                return src
            include_path = path.parent.joinpath(src[1:])
            logging.debug(
                "Will include file %s to %s",
                include_path.absolute().resolve(),
                path.absolute().resolve(),
            )
            return self._load_yaml_from_file(include_path, env, visited + [path])

        if not path.exists():
            raise YamlFileNotFound(path)

        if not path.is_file():
            raise YamlNotReadableFile(path)

        if path in visited:
            raise YamlCycleReferenceError(path)

        content = (
            path.read_text()
            .replace(self._include_marker, self._include_substitution)
            .replace(self._variable_markers[0], self._variable_substitutions[0])
            .replace(self._variable_markers[1], self._variable_substitutions[1])
        )

        yml = yaml.full_load(content)
        return walk(yml, resolve_include)

    def _resolve_variables(self, process, env, path):
        vars_re = re.compile(
            rf"{self._variable_substitutions[0]}(.*?){self._variable_substitutions[1]}"
        )

        def loop(s):
            if not isinstance(s, str):
                return s

            found_vars = re.findall(vars_re, s)
            if not found_vars:
                return s

            for found_var in found_vars:
                if found_var not in env:
                    raise YamlUnknownVariableError(path, found_var)

                substitution = env.get(found_var)
                if substitution is None:
                    raise YamlUndefinedVariableError(path, found_var)

                if (
                    s
                    == f"{self._variable_substitutions[0]}{found_var}{self._variable_substitutions[1]}"
                ):
                    s = env.get(found_var)
                else:
                    if type(substitution) in (list, dict):
                        raise YamlIncorrectSubstitutionError(
                            path, found_var, substitution
                        )
                    s = s.replace(
                        f"{self._variable_substitutions[0]}{found_var}{self._variable_substitutions[1]}",
                        str(substitution),
                    )
            return s

        return walk(process, loop)


class YamlError(Exception):
    def __init__(self, file: Path):
        self.file = file


class YamlFileNotFound(YamlError):
    def __str__(self):
        return f"File {self.file.absolute()} is not found"


class YamlNotReadableFile(YamlError):
    def __str__(self):
        return f"File {self.file.absolute()} can not be read"


class YamlCycleReferenceError(YamlError):
    def __str__(self):
        return f"File {self.file.absolute()} is referenced in cycle"


class YamlUnknownVariableError(YamlError):
    def __init__(self, file: Path, variable: str):
        super(YamlUnknownVariableError, self).__init__(file)
        self._variable = variable

    def __str__(self):
        return f"Variable {self._variable} (in {self.file}) is not found in provided environment"


class YamlUndefinedVariableError(YamlError):
    def __init__(self, file: Path, variable: str):
        super(YamlUndefinedVariableError, self).__init__(file)
        self._variable = variable

    def __str__(self):
        return (
            f"Variable {self._variable} (in {self.file}) is not defined (i.e. `VAR: `),"
            f" explicit value required (i.e. `VAR: []`)"
        )


class YamlIncorrectSubstitutionError(YamlError):
    def __init__(self, file: Path, variable: str, value: dict):
        super(YamlIncorrectSubstitutionError, self).__init__(file)
        self._variable = variable
        self._value = value

    def __str__(self):
        return f"Variable {self._variable} can not be resolved in given context by {self._value} in {self.file}"


class YamlInvalidFormatError(YamlError):
    def __init__(self, file: Path, message: str):
        super(YamlInvalidFormatError, self).__init__(file)
        self.message = message

    def __str__(self):
        return f"{self.message} in {self.file.absolute()}"


def load_yaml(file_path: Path, loader: YamlLoader, env: dict) -> dict:
    return loader.load_yaml_from_file(file_path, env)


def load_manifest(file_path: Path, loader: YamlLoader, env: dict) -> Envelope:
    try:
        manifest = load_yaml(file_path, loader, env)
        return Envelope.from_manifest(manifest)
    except ValueError as e:
        raise YamlInvalidFormatError(file_path, str(e))
