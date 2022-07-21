from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from clin.models.shared import Envelope, Kind
from clin.yamlops import YamlLoader


@dataclass
class Process:
    id: str
    path: str
    envelope: Envelope
    target: str


def calculate_scope(
    master: dict,
    base_path: Path,
    loader: YamlLoader,
    filter_id: tuple[str],
    filter_env: tuple[str],
) -> dict[Kind, list[Process]]:
    processes = master.get("process")
    if not processes:
        raise Exception("'process' section is not found")

    scope = {kind: [] for kind in Kind}
    for proc in processes:
        if len(filter_id) > 0 and proc["id"] not in filter_id:
            continue
        if len(filter_env) > 0 and proc["target"] not in filter_env:
            continue

        proc_id = proc["id"]
        sources = [base_path.joinpath(s).resolve(strict=False) for s in proc["paths"]]
        manifests_files = []
        for source in sources:
            if not source.exists():
                raise Exception(
                    f"Specified path 'f{source.absolute()}' is not found for process '{proc_id}'"
                )

            manifests_files += sorted(
                chain(source.glob("*.yml"), source.glob("*.yaml"))
            )
            if not manifests_files:
                logging.warning(
                    "No manifests found for process '%s' in '%s'",
                    proc_id,
                    source.absolute(),
                )

        for manifest_file in manifests_files:
            manifest = loader.load_yaml_from_file(manifest_file, proc.get("env", {}))
            envelope = Envelope.from_manifest(manifest)
            scope[envelope.kind].append(
                Process(
                    id=proc_id,
                    path=manifest_file,
                    envelope=envelope,
                    target=proc["target"],
                )
            )

    return scope
