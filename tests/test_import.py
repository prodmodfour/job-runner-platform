from __future__ import annotations

import job_runner_platform


def test_package_imports() -> None:
    assert job_runner_platform.__version__ == "0.1.0"
