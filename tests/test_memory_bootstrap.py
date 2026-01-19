from __future__ import annotations

from pathlib import Path

import pytest

from memory_service.memory_bootstrap import run_bootstrap


def test_bootstrap_runs_without_modules():
    report = run_bootstrap(modules=[])  # skip module import checks
    assert report.repo_root.is_dir()
    assert isinstance(report.missing_modules, list)
    assert report.config_path.name == "memory_config.yaml"


@pytest.mark.parametrize(
    "config_rel",
    [
        "config/memory_config.yaml",
        "Config/memory_config.yaml",  # accommodate older casing just in case
    ],
)
def test_bootstrap_config_detection(config_rel: str):
    report = run_bootstrap(modules=[], config_relative_path=config_rel)
    assert isinstance(report.config_exists, bool)
    # Path should point somewhere under the repo even if the file is absent.
    assert Path(report.config_path).is_absolute()

