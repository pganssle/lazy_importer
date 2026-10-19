"""Covers the documented behavior specific to the compatibility context."""

import builtins
import textwrap
from collections.abc import Callable
from typing import Final

import pytest

pytestmark: Final = pytest.mark.skipif(
    hasattr(builtins, "__lazy_import__"), reason="fallback-specific behavior"
)


def test_nested_context_masks_and_restores_selection(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import builtins, sys
            from lazy_importer import lazy_importer
            original = builtins.__import__
            with lazy_importer({'example_pkg'}):
                with lazy_importer(set()):
                    import example_pkg.child
                import example_pkg as alias
            assert globals()['alias'] is not sys.modules['example_pkg']
            assert alias.answer == 42
            assert builtins.__import__ is original
        """)
    )


def test_global_aliases_are_replaced(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys
            from lazy_importer import lazy_importer, resolve
            with lazy_importer({'example_pkg'}):
                import example_pkg as first
            second = first
            proxies = [first]
            assert 'example_pkg' not in sys.modules
            module = resolve(first)
            assert first is module
            assert second is module
            assert resolve(proxies[0]) is module
        """)
    )


def test_replaced_hook_is_not_clobbered(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import builtins
        from typing import Any

        import lazy_importer

        original = builtins.__import__

        def replacement(*args: Any, **kwargs: Any) -> Any:
            return original(*args, **kwargs)

        with lazy_importer.lazy_importer({"example_pkg"}):
            builtins.__import__ = replacement
        assert builtins.__import__ is replacement

    run(scenario)


def test_overlapping_threads_restore_hook_at_last_exit(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import builtins
        import threading

        import lazy_importer

        original = builtins.__import__
        entered = threading.Event()
        leave = threading.Event()
        results = []

        def worker() -> None:
            with lazy_importer.lazy_importer({"example_pkg"}):
                import example_pkg

                results.append(type(example_pkg).__name__ != "module")
                entered.set()
                assert leave.wait(5)
            results.append(lazy_importer.resolve(example_pkg).answer)

        with lazy_importer.lazy_importer({"example_pkg"}):
            thread = threading.Thread(target=worker)
            thread.start()
            assert entered.wait(5)
        assert builtins.__import__ is not original
        leave.set()
        thread.join(5)
        assert not thread.is_alive()
        assert results == [True, 42]
        assert builtins.__import__ is original

    run(scenario)


def test_circular_resolution_raises_and_can_retry(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import builtins
        from typing import Any

        import lazy_importer

        with lazy_importer.lazy_importer({"example_pkg"}):
            import example_pkg
        original = builtins.__import__

        def recursive(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "example_pkg":
                return lazy_importer.resolve(example_pkg)
            return original(name, *args, **kwargs)

        builtins.__import__ = recursive
        try:
            lazy_importer.resolve(example_pkg)
        except ImportError as exc:
            assert "circular lazy import" in str(exc)
        else:
            raise AssertionError("recursive resolution succeeded")
        finally:
            builtins.__import__ = original
        assert lazy_importer.resolve(example_pkg).answer == 42

    run(scenario)


def test_relative_import_uses_spec_when_package_is_absent(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import importlib.machinery, sys
            from lazy_importer import lazy_importer
            __package__ = None
            __spec__ = importlib.machinery.ModuleSpec('example_pkg.client', None)
            with lazy_importer({'example_pkg.child'}):
                from .child import value
            assert 'example_pkg' not in sys.modules
            assert value == 17
        """)
    )


@pytest.mark.parametrize("package", [False, True])
def test_relative_import_uses_module_name_as_last_resort(
    run: Callable[[str | Callable[[], None]], None], package: bool
) -> None:
    run(
        textwrap.dedent(f"""
            import sys
            from lazy_importer import lazy_importer
            __package__ = None
            __spec__ = None
            __name__ = {'"example_pkg"' if package else '"example_pkg.client"'}
            if {package}:
                __path__ = []
            with lazy_importer({{'example_pkg.child'}}):
                from .child import value
            assert 'example_pkg' not in sys.modules
            assert value == 17
        """)
    )


def test_import_without_namespace_remains_eager(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import builtins
        import sys

        import lazy_importer

        with lazy_importer.lazy_importer({"example_pkg"}):
            module = builtins.__import__("example_pkg")
        assert module is sys.modules["example_pkg"]

    run(scenario)


def test_call_while_context_active_keeps_dependencies_eager(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import sys

        import lazy_importer

        with lazy_importer.lazy_importer({"eager_dep", "example_pkg"}):
            import eager_dep

            assert "eager_dep" not in sys.modules
            module = lazy_importer.resolve(eager_dep)
        assert type(module.example_pkg).__name__ == "module"
        assert module.example_pkg.answer == 42

    run(scenario)
