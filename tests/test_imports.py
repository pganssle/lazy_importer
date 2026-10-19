"""Exercises the common public contract on fallback and native runtimes."""

from collections.abc import Callable

import pytest


@pytest.mark.parametrize(
    "statement, expression, expected",
    [
        ("import example_pkg", "example_pkg.answer", "42"),
        ("import example_pkg as alias", "alias.answer", "42"),
        ("from example_pkg import double", "double(6)", "12"),
        ("from example_pkg import answer as alias", "alias + 1", "43"),
        ("import example_pkg.child", "example_pkg.child.value", "17"),
        ("import example_pkg.child as alias", "alias.value", "17"),
        ("from example_pkg import child", "child.value", "17"),
        ("from example_pkg.child import value", "value + 1", "18"),
    ],
)
def test_import_defers_execution(
    run: Callable[[str], None], statement: str, expression: str, expected: str
) -> None:
    run(f"""
        import sys
        from lazy_importer import lazy_importer
        __lazy_modules__ = {{'example_pkg', 'example_pkg.child'}}
        with lazy_importer(__lazy_modules__):
            {statement}
        assert 'example_pkg' not in sys.modules
        assert ({expression}) == {expected}
        assert 'example_pkg' in sys.modules
    """)


def test_each_from_name_resolves_independently(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import answer, other
        proxies = [globals()['answer'], globals()['other']]
        assert resolve(proxies[0]) == 42
        assert globals()['other'] is proxies[1]
        sys.modules['example_pkg'].other = 99
        assert resolve(proxies[1]) == 99
        assert resolve(proxies[1]) == 99
    """)


def test_failed_import_can_retry(run: Callable[[str], None]) -> None:
    run("""
        import sys, types
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'missing_pkg'}
        with lazy_importer(__lazy_modules__):
            import missing_pkg
        proxy = globals()['missing_pkg']
        try:
            resolve(proxy)
        except ModuleNotFoundError as exc:
            assert exc.name == 'missing_pkg'
        else:
            raise AssertionError('missing import succeeded')
        module = types.ModuleType('missing_pkg')
        sys.modules['missing_pkg'] = module
        assert resolve(proxy) is module
    """)


def test_module_exception_propagates_at_use(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'broken'}
        with lazy_importer(__lazy_modules__):
            import broken
        assert 'broken' not in sys.modules
        try:
            resolve(globals()['broken'])
        except RuntimeError as exc:
            assert str(exc) == 'broken'
        else:
            raise AssertionError('module exception was lost')
        assert 'broken' not in sys.modules
    """)


def test_missing_from_attribute_is_import_error(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import missing
        try:
            resolve(globals()['missing'])
        except ImportError as exc:
            assert 'missing' in str(exc)
        else:
            raise AssertionError('missing attribute succeeded')
    """)


def test_relative_import(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __package__ = 'example_pkg'
        __lazy_modules__ = {'example_pkg.child'}
        with lazy_importer(__lazy_modules__):
            from .child import value
        assert 'example_pkg' not in sys.modules
        assert value + 1 == 18
    """)


def test_star_import_is_eager(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import *
        assert 'example_pkg' in sys.modules
        assert answer == 42
    """)


def test_selection_is_exact_and_dependencies_are_eager(
    run: Callable[[str], None],
) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import eager_dep
        assert 'example_pkg' in sys.modules
        assert type(eager_dep.example_pkg).__name__ == 'module'
    """)


def test_dotted_siblings_are_available(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __lazy_modules__ = {'example_pkg.child', 'example_pkg.sibling'}
        with lazy_importer(__lazy_modules__):
            import example_pkg.child
            import example_pkg.sibling
        assert 'example_pkg' not in sys.modules
        assert example_pkg.child.value == 17
        assert example_pkg.sibling.value == 18
    """)


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("bool(items)", "True"),
        ("list(items)", "[1, 2]"),
        ("len(items)", "2"),
        ("items[0]", "1"),
        ("2 in items", "True"),
        ("str(answer)", "'42'"),
        ("repr(answer)", "'42'"),
        ("int(answer)", "42"),
        ("hash(answer)", "hash(42)"),
        ("answer * 2", "84"),
        ("2 + answer", "44"),
        ("answer + other", "85"),
        ("answer < other", "True"),
        ("round(answer)", "42"),
    ],
)
def test_proxy_operations(
    run: Callable[[str], None], expression: str, expected: str
) -> None:
    run(f"""
        from lazy_importer import lazy_importer
        __lazy_modules__ = {{'example_pkg'}}
        with lazy_importer(__lazy_modules__):
            from example_pkg import items, answer, other
        assert ({expression}) == {expected}
    """)


def test_class_base(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import Example
        class Child(Example): pass
        assert issubclass(Child, resolve(Example))
    """)


def test_hook_restored_after_exception(run: Callable[[str], None]) -> None:
    run("""
        import builtins
        from lazy_importer import lazy_importer
        original = builtins.__import__
        try:
            with lazy_importer({'example_pkg'}):
                raise ValueError('body')
        except ValueError:
            pass
        assert builtins.__import__ is original
    """)


@pytest.mark.parametrize(
    "value, error",
    [
        ("'abc'", "TypeError"),
        ("[1]", "TypeError"),
        ("['']", "ValueError"),
        ("['.relative']", "ValueError"),
        ("['a..b']", "ValueError"),
        ("['a-b']", "ValueError"),
    ],
)
def test_invalid_selection_leaves_hook_unchanged(
    run: Callable[[str], None], value: str, error: str
) -> None:
    run(f"""
        import builtins
        from lazy_importer import lazy_importer
        original = builtins.__import__
        try:
            lazy_importer({value})
        except {error} as exc:
            assert 'expected' in str(exc)
        else:
            raise AssertionError('invalid argument accepted')
        assert builtins.__import__ is original
    """)


def test_resolution_uses_current_import_hook(run: Callable[[str], None]) -> None:
    run("""
        import builtins
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import example_pkg
        original = builtins.__import__
        calls = []
        def importing(name, *args, **kwargs):
            calls.append(name)
            return original(name, *args, **kwargs)
        builtins.__import__ = importing
        assert resolve(globals()['example_pkg']).answer == 42
        assert 'example_pkg' in calls
    """)


def test_thread_context_does_not_leak(run: Callable[[str], None]) -> None:
    run("""
        import builtins, threading, sys
        from lazy_importer import lazy_importer
        original = builtins.__import__
        results = []
        def worker():
            import example_pkg
            results.append(type(example_pkg).__name__)
        with lazy_importer({'example_pkg'}):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(5)
            assert not thread.is_alive()
        assert results == ['module']
        assert builtins.__import__ is original
    """)


def test_concurrent_resolution_returns_one_module(run: Callable[[str], None]) -> None:
    run("""
        import concurrent.futures
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import example_pkg
        proxy = globals()['example_pkg']
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(resolve, [proxy] * 32))
        assert all(result is results[0] for result in results)
        assert results[0].answer == 42
    """)


def test_imported_attributes_do_not_collide_with_proxy_state(
    run: Callable[[str], None],
) -> None:
    run("""
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import __name__, __dict__
        assert resolve(globals()['__name__']) == 'example_pkg'
        assert resolve(globals()['__dict__'])['answer'] == 42
    """)


def test_proxy_mutation_and_inplace_operations(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import example_pkg as alias
            from example_pkg import items, answer
        alias.extra = 8
        assert alias.extra == 8
        del alias.extra
        assert not hasattr(alias, 'extra')
        items[0] = 9
        del items[1]
        assert resolve(items) == [9]
        answer += 2
        assert answer == 44
    """)


def test_rebinding_does_not_overwrite_new_value(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import example_pkg
        proxies = [globals()['example_pkg']]
        example_pkg = 'replacement'
        assert resolve(proxies[0]).answer == 42
        assert example_pkg == 'replacement'
    """)


def test_relative_package_from_import(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __package__ = 'example_pkg'
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from . import child
        assert 'example_pkg' not in sys.modules
        assert child.value == 17
    """)


def test_parent_resolves_without_loading_pending_sibling(
    run: Callable[[str], None],
) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg.child', 'example_pkg.sibling'}
        with lazy_importer(__lazy_modules__):
            import example_pkg.child
            import example_pkg.sibling
        assert example_pkg.answer == 42
        assert 'example_pkg.child' not in sys.modules
        assert example_pkg.child.value == 17
        assert example_pkg.sibling.value == 18
        assert resolve(example_pkg.sibling) is sys.modules['example_pkg.sibling']
    """)


def test_eager_import_does_not_resolve_from_binding(run: Callable[[str], None]) -> None:
    run("""
        import importlib, sys
        from lazy_importer import lazy_importer, resolve
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import answer
        proxies = [globals()['answer']]
        module = importlib.import_module('example_pkg')
        module.answer = 100
        assert globals()['answer'] is proxies[0]
        assert resolve(proxies[0]) == 100
    """)


def test_selected_prefix_does_not_select_submodule(run: Callable[[str], None]) -> None:
    run("""
        import sys
        from lazy_importer import lazy_importer
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            import example_pkg.child
        assert 'example_pkg.child' in sys.modules
    """)


def test_relative_import_retains_original_package(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer
        __package__ = 'example_pkg'
        __lazy_modules__ = {'example_pkg.child'}
        with lazy_importer(__lazy_modules__):
            from .child import value
        __package__ = 'different_package'
        assert value == 17
    """)


def test_callable_resolves_lazy_arguments(run: Callable[[str], None]) -> None:
    run("""
        from lazy_importer import lazy_importer
        __lazy_modules__ = {'example_pkg'}
        with lazy_importer(__lazy_modules__):
            from example_pkg import double, answer
        assert double(value=answer) == 84
    """)
