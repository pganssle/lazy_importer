"""Checks that native interpreter policy remains authoritative."""

import builtins
import textwrap
from collections.abc import Callable
from typing import Final

import pytest

pytestmark: Final = pytest.mark.skipif(
    not hasattr(builtins, "__lazy_import__"), reason="requires native lazy imports"
)


def test_native_filter_can_force_eager_imports(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys, builtins
            from lazy_importer import lazy_importer
            original = builtins.__import__
            __lazy_modules__ = {'example_pkg'}
            sys.set_lazy_imports_filter(lambda importer, name, fromlist: False)
            with lazy_importer(__lazy_modules__):
                import example_pkg
            assert 'example_pkg' in sys.modules
            assert builtins.__import__ is original
            assert example_pkg.answer == 42
        """)
    )


def test_native_path_requires_module_declaration(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys, builtins
            from lazy_importer import lazy_importer
            original = builtins.__import__
            with lazy_importer({'example_pkg'}):
                import example_pkg
            assert 'example_pkg' in sys.modules
            assert builtins.__import__ is original
        """)
    )
