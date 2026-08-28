from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

SCIENTIFIC_CONFIG_FILES = (
    "indicator_register.yaml",
    "period_panel.yaml",
    "protocol.yaml",
    "facilities.yaml",
    "queries.yaml",
    "expected_baselines.yaml",
    "milestones.yaml",
    "priors.yaml",
    "interpretation_protocol.yaml",
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_yaml_scalars(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_yaml_scalars(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return normalize_yaml_scalars(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported YAML scalar: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    normalized = normalize_yaml_scalars(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def scientific_config_hashes(
    config_dir: Path,
    filenames: Iterable[str] = SCIENTIFIC_CONFIG_FILES,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for filename in filenames:
        path = config_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing scientific configuration: {path}")
        hashes[filename] = canonical_sha256(load_yaml(path))
    return hashes


def combined_protocol_hash(config_hashes: dict[str, str]) -> str:
    return canonical_sha256(config_hashes)
