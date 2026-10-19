"""Exercises imports in fresh processes to isolate global import state."""

import inspect
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def run(tmp_path: Path) -> Callable[[str | Callable[[], None]], None]:
    package = tmp_path / "example_pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        textwrap.dedent("""
            answer = 42
            other = 43
            items = [1, 2]

            def double(value):
                return value * 2

            class Example:
                pass
        """),
        encoding="utf-8",
    )
    (package / "child.py").write_text("value = 17\n", encoding="utf-8")
    (package / "sibling.py").write_text("value = 18\n", encoding="utf-8")
    (tmp_path / "eager_dep.py").write_text(
        textwrap.dedent("""
            import example_pkg

            assert example_pkg.answer == 42
        """),
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text(
        "raise RuntimeError('broken')\n", encoding="utf-8"
    )

    (tmp_path / "dynamic_mod.py").write_text(
        textwrap.dedent("""
            def __getattr__(name):
                if name != "value":
                    raise AttributeError(name)
                import example_pkg
                return example_pkg
        """),
        encoding="utf-8",
    )

    def execute(scenario: str | Callable[[], None]) -> None:
        if isinstance(scenario, str):
            source = scenario
        else:
            source = textwrap.dedent(inspect.getsource(scenario))
            source += f"\n{scenario.__name__}()\n"
        script = tmp_path / "scenario.py"
        script.write_text(source, encoding="utf-8")
        env = dict(os.environ)
        # Installed package paths stay available; only fixture modules are added.
        env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    return execute
