"""Reader for ``manifest.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Artifact:
    version: str
    url: str
    sha256: str


@dataclass(frozen=True)
class Model:
    kind: str  # small | default | large
    tag: str
    size_gb: float


@dataclass(frozen=True)
class Manifest:
    data: dict[str, object]

    @property
    def min_free_gb(self) -> float:
        return float(self.data["min_free_gb"])  # type: ignore[arg-type]

    @property
    def port_range(self) -> tuple[int, int]:
        rng: list[int] = self.data["port_range"]  # type: ignore[assignment]
        return int(rng[0]), int(rng[1])

    def model(self, kind: str) -> Model:
        models: dict[str, dict[str, object]] = self.data["models"]  # type: ignore[assignment]
        entry = models[kind]
        return Model(kind, str(entry["tag"]), float(entry["size_gb"]))  # type: ignore[arg-type]

    @property
    def ollama_host(self) -> str:
        section: dict[str, str] = self.data["ollama"]  # type: ignore[assignment]
        return section["host"]

    def artifact(self, component: str, platform: str) -> Artifact:
        section: dict[str, object] = self.data[component]  # type: ignore[assignment]
        platforms: dict[str, dict[str, str]] = section["platforms"]  # type: ignore[assignment]
        if platform not in platforms:
            raise KeyError(f"{component}: no build for {platform}")
        entry = platforms[platform]
        return Artifact(str(section["version"]), entry["url"], entry["sha256"])


def load_manifest(path: Path) -> Manifest:
    with path.open("rb") as fh:
        return Manifest(tomllib.load(fh))
