"""Covers the documented behavior specific to the compatibility context."""

import builtins
from collections.abc import Callable
from typing import Final

import pytest

pytestmark: Final = pytest.mark.skipif(
    hasattr(builtins, "__lazy_import__"), reason="fallback-specific behavior"
)


def test_nested_context_masks_and_restores_selection(
    run: Callable[[str], None],
) -> None:
    run("""
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


def test_global_aliases_are_replaced(run: Callable[[str], None]) -> None:
    run("""
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


def test_replaced_hook_is_not_clobbered(run: Callable[[str], None]) -> None:
    run("""
        import builtins
        from lazy_importer import lazy_importer
        original = builtins.__import__
        def replacement(*args, **kwargs):
            return original(*args, **kwargs)
        with lazy_importer({'example_pkg'}):
            builtins.__import__ = replacement
        assert builtins.__import__ is replacement
    """)


def test_overlapping_threads_restore_hook_at_last_exit(
    run: Callable[[str], None],
) -> None:
    run("""
        import builtins, threading, sys
        from lazy_importer import lazy_importer, resolve
        original = builtins.__import__
        entered = threading.Event()
        leave = threading.Event()
        results = []
        def worker():
            with lazy_importer({'example_pkg'}):
                import example_pkg
                results.append(type(example_pkg).__name__ != 'module')
                entered.set()
                assert leave.wait(5)
            results.append(resolve(example_pkg).answer)
        with lazy_importer({'example_pkg'}):
            thread = threading.Thread(target=worker)
            thread.start()
            assert entered.wait(5)
        assert builtins.__import__ is not original
        leave.set()
        thread.join(5)
        assert not thread.is_alive()
        assert results == [True, 42]
        assert builtins.__import__ is original
    """)


def test_circular_resolution_raises_and_can_retry(run: Callable[[str], None]) -> None:
    run("""
        import builtins
        from lazy_importer import lazy_importer, resolve
        with lazy_importer({'example_pkg'}):
            import example_pkg
        original = builtins.__import__
        def recursive(name, *args, **kwargs):
            if name == 'example_pkg':
                return resolve(example_pkg)
            return original(name, *args, **kwargs)
        builtins.__import__ = recursive
        try:
            resolve(example_pkg)
        except ImportError as exc:
            assert 'circular lazy import' in str(exc)
        else:
            raise AssertionError('recursive resolution succeeded')
        finally:
            builtins.__import__ = original
        assert resolve(example_pkg).answer == 42
    """)


def test_relative_import_uses_spec_when_package_is_absent(
    run: Callable[[str], None],
) -> None:
    run("""
        import importlib.machinery, sys
        from lazy_importer import lazy_importer
        __package__ = None
        __spec__ = importlib.machinery.ModuleSpec('example_pkg.client', None)
        with lazy_importer({'example_pkg.child'}):
            from .child import value
        assert 'example_pkg' not in sys.modules
        assert value == 17
    """)


@pytest.mark.parametrize("package", [False, True])
def test_relative_import_uses_module_name_as_last_resort(
    run: Callable[[str], None], package: bool
) -> None:
    run(f"""
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


def test_import_without_namespace_remains_eager(run: Callable[[str], None]) -> None:
    run("""
        import builtins, sys
        from lazy_importer import lazy_importer
        with lazy_importer({'example_pkg'}):
            module = builtins.__import__('example_pkg')
        assert module is sys.modules['example_pkg']
    """)


def test_call_while_context_active_keeps_dependencies_eager(
    run: Callable[[str], None],
) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer, resolve
        with lazy_importer({'eager_dep', 'example_pkg'}):
            import eager_dep
            assert 'eager_dep' not in sys.modules
            module = resolve(eager_dep)
        assert type(module.example_pkg).__name__ == 'module'
        assert module.example_pkg.answer == 42
    """)
