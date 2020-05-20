import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import List

from clin.yamlops import YamlLoader


@dataclass
class Process:
    id: str
    path: str
    kind: str
    spec: dict
    target: str


def calculate_scope(master: dict, base_path: Path, loader: YamlLoader) -> List[Process]:
    processes = master.get("process")
    if not processes:
        raise Exception("'process' section is not found")

    scope = []
    for proc in processes:
        proc_id = proc["id"]
        proc_paths = proc["paths"]

        sources = [base_path.joinpath(s).resolve(strict=False) for s in proc_paths]
        manifests_files = []
        for source in sources:
            if not source.exists():
                raise Exception(
                    f"Specified path 'f{source.absolute()}' is not found for process '{proc_id}'"
                )

            manifests_files += chain(source.glob("*.yml"), source.glob("*.yaml"))
            if not manifests_files:
                logging.warning(
                    "No manifests found for process '%s' in '%s'",
                    proc_id,
                    source.absolute(),
                )

        for manifest_file in manifests_files:
            yml = loader.load_yaml_from_file(manifest_file, proc.get("env", {}))

            kind = yml.get("kind")
            if not kind:
                raise Exception(
                    f"Manifest file '{manifest_file}' for process '{proc_id}' is malformed, required field `kind` is not found"
                )

            spec = yml.get("spec")
            if not spec:
                raise Exception(
                    f"Manifest file '{manifest_file}' for process '{proc_id}' is malformed, required field `spec` is not found"
                )

            scope.append(
                Process(
                    id=proc_id,
                    path=manifest_file,
                    kind=kind,
                    spec=spec,
                    target=proc["target"],
                )
            )
    return scope
