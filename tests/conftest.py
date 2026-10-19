"""Exercises imports in fresh processes to isolate global import state."""

import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def run(tmp_path: Path) -> Callable[[str], None]:
    package = tmp_path / "example_pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        "answer = 42\nother = 43\nitems = [1, 2]\n"
        "def double(value): return value * 2\n"
        "class Example: pass\n",
        encoding="utf-8",
    )
    (package / "child.py").write_text("value = 17\n", encoding="utf-8")
    (package / "sibling.py").write_text("value = 18\n", encoding="utf-8")
    (tmp_path / "eager_dep.py").write_text(
        "import example_pkg\nassert example_pkg.answer == 42\n", encoding="utf-8"
    )
    (tmp_path / "broken.py").write_text(
        "raise RuntimeError('broken')\n", encoding="utf-8"
    )

    def execute(source: str) -> None:
        env = dict(os.environ)
        # Installed package paths stay available; only fixture modules are added.
        env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(source)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    return execute
