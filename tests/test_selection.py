"""Checks declaration-based import selection on fallback and native runtimes."""

import textwrap
from collections.abc import Callable


def test_missing_declaration_keeps_imports_eager(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys
            from lazy_importer import lazy_importer
            with lazy_importer():
                import example_pkg
            assert 'example_pkg' in sys.modules
            assert example_pkg is sys.modules['example_pkg']
        """)
    )


def test_declaration_is_read_at_each_import(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys
            from lazy_importer import lazy_importer
            context = lazy_importer()
            __lazy_modules__ = set()
            with context:
                __lazy_modules__.add('example_pkg.child')
                from example_pkg.child import value
                assert 'example_pkg' not in sys.modules
                __lazy_modules__ = {'broken'}
                import broken
                assert 'broken' not in sys.modules
                __lazy_modules__.clear()
                import example_pkg.sibling
                assert 'example_pkg.sibling' in sys.modules
                del __lazy_modules__
                import eager_dep
                assert 'eager_dep' in sys.modules
            assert value == 17
        """)
    )


def test_custom_membership_does_not_require_iteration(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys
            from lazy_importer import lazy_importer
            calls = []

            class Selection:
                def __contains__(self, name):
                    import math
                    calls.append(name)
                    return name.startswith('example_pkg.')

                def __iter__(self):
                    raise AssertionError('selection must not be iterated')

            __lazy_modules__ = Selection()
            with lazy_importer():
                from example_pkg.child import value
            assert calls == ['example_pkg.child']
            assert 'example_pkg' not in sys.modules
            assert value == 17
        """)
    )


def test_selection_uses_the_importing_namespace(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    def scenario() -> None:
        import runpy
        import sys
        import textwrap
        from pathlib import Path

        from lazy_importer import lazy_importer, resolve

        Path("other_module.py").write_text(
            textwrap.dedent("""
                __lazy_modules__ = {'example_pkg.child'}
                from example_pkg.child import value
            """),
            encoding="utf-8",
        )
        globals()["__lazy_modules__"] = {"broken"}
        with lazy_importer():
            namespace = runpy.run_path("other_module.py")
        assert "example_pkg" not in sys.modules
        assert resolve(namespace["value"]) == 17

    run(scenario)


def test_star_import_does_not_consult_declaration(
    run: Callable[[str | Callable[[], None]], None],
) -> None:
    run(
        textwrap.dedent("""
            import sys
            from lazy_importer import lazy_importer

            class Selection:
                def __contains__(self, name):
                    raise AssertionError('star imports must remain eager')

            __lazy_modules__ = Selection()
            with lazy_importer():
                from example_pkg import *
            assert 'example_pkg' in sys.modules
            assert answer == 42
        """)
    )
