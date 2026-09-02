"""Shared Neo4j connection configuration.

Values are loaded once from ``neo4j.env`` in the project root and may be
overridden by real environment variables. Keeping this in one ignored local file
avoids repeating credentials on every detector/import command.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "neo4j.env"


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str | None = None


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_neo4j_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
    environ: Mapping[str, str] | None = None,
) -> Neo4jConfig:
    file_values = _read_env_file(Path(path))
    environment = os.environ if environ is None else environ

    def get(name: str, default: str = "") -> str:
        return environment.get(name) or file_values.get(name) or default

    return Neo4jConfig(
        uri=get("NEO4J_URI", "bolt://localhost:7687"),
        user=get("NEO4J_USER", "neo4j"),
        password=get("NEO4J_PASSWORD", ""),
        database=get("NEO4J_DATABASE") or None,
    )


NEO4J_CONFIG = load_neo4j_config()
