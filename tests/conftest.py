# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
