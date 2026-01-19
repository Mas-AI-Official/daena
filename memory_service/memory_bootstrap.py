"""
Bootstrap + configuration helpers for the NBMF memory subsystem.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml  # type: ignore[import-untyped]


DEFAULT_MODULES: List[str] = [
    "memory_service.nbmf_encoder",
    "memory_service.nbmf_decoder",
    "memory_service.router",
    "memory_service.caching_cas",
    "memory_service.simhash_neardup",
    "memory_service.ledger",
    "memory_service.delta_encoding",
    "memory_service.quantized_latents",
    "memory_service.quarantine_l2q",
    "memory_service.trust_manager",
    "memory_service.emotion5d",
    "memory_service.expression_adapter",
]


def _config_path() -> Path:
    env_path = os.getenv("DAENA_MEMORY_CONFIG")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[1] / "config" / "memory_config.yaml"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_file = path or _config_path()
    if not config_file.exists():
        return {}
    text = config_file.read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    config_file = path or _config_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


@dataclass
class BootstrapReport:
    repo_root: Path
    config_exists: bool
    config_path: Path
    missing_modules: List[str]
    python_version: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["repo_root"] = str(payload["repo_root"])
        payload["config_path"] = str(payload["config_path"])
        return payload


def discover_repo_root(start: Path | None = None) -> Path:
    """
    Walk upwards from the given directory until we find the `Daena` root.
    If not found, default to the caller's directory.
    """
    current = start or Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "config").is_dir() and (parent / "README.md").exists():
            return parent
    return current


def check_modules(modules: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError:
            missing.append(mod)
    return missing


def run_bootstrap(
    modules: Iterable[str] | None = None,
    config_relative_path: str = "config/memory_config.yaml",
) -> BootstrapReport:
    repo_root = discover_repo_root()
    modules = list(modules or DEFAULT_MODULES)
    missing_modules = check_modules(modules)
    config_path = repo_root / config_relative_path
    config_exists = config_path.exists()

    return BootstrapReport(
        repo_root=repo_root,
        config_exists=config_exists,
        config_path=config_path,
        missing_modules=missing_modules,
        python_version=".".join(map(str, sys.version_info[:3])),
    )


def main(argv: List[str] | None = None) -> int:
    report = run_bootstrap()
    print(json.dumps(report.to_dict(), indent=2))
    if report.missing_modules:
        return 1
    if not report.config_exists:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

