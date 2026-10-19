"""Verifies that free-threaded matrix jobs actually exercise that runtime."""

import os
from collections.abc import Callable

import pytest


@pytest.mark.skipif(
    os.environ.get("LAZY_IMPORTER_TEST_FREE_THREADED") != "1",
    reason="requires a free-threaded matrix job",
)
def test_free_threaded_runtime_has_gil_disabled(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import sys
        import sysconfig

        assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
        assert not sys._is_gil_enabled()

    run(scenario)
