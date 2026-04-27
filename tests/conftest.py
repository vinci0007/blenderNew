from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


_WORKSPACE_TMP = Path(".tmp_pytest_workspace")


@pytest.fixture
def tmp_path():
    """Workspace-local replacement for pytest's default tmp_path fixture.

    Some Windows environments in this project cannot access the system temp
    directory used by pytest. Keeping test temp files inside the repository
    makes these tests deterministic in local runs and CI-like sandboxes.
    """
    _WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)
    path = _WORKSPACE_TMP / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
