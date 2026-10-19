# Development

Use an isolated environment:

```sh
uv sync --group test --group lint
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
```

`uv.lock` records the development dependency resolution. Runtime dependencies
are empty; consumers aren't constrained by this development lockfile.

Run the installed-wheel test matrix with `uvx tox`. It targets Python 3.11 through 3.15, plus the
3.14 and 3.15 free-threaded builds and linting. The free-threaded environments
set `PYTHON_GIL=0` and verify that the child interpreters have the GIL disabled. Missing interpreters cause a failed environment;
they aren't silently skipped. Individual environments can be selected with
`uvx tox -e py313`.

Tests create small packages in temporary directories and exercise the public
API in fresh processes. Shared tests run against both the fallback and native
runtime behavior. Fallback-specific tests are explicitly marked, since that
path isn't used when native lazy imports are available. Import-state tests
should stay isolated so an earlier test can't make a deferred import appear
successful by preloading its dependency.

For branch coverage, run `uv run pytest --cov --cov-report=term-missing`.
Coverage's subprocess support captures the child interpreters. The parent test
process may report that it didn't import the package; that is expected for
these isolated tests. Native-only branches require a Python 3.15+ coverage run.

Build distributions with `uv build`. Check both the wheel and source archive;
the source archive includes tests and the wheel includes the license and
`py.typed` marker. Keep packaging, behavioral changes with their tests, and
unrelated documentation changes in separate commits.

## Design constraints

The public surface is `lazy_importer(modules)` and `resolve(value)`. The
fallback uses the documented import hook to create proxies and suspends
selection while executing an import. Hook lifetime is synchronized across
threads, while each thread owns its stack of active selections. Proxy locks
protect publication of a resolved value, but aren't held while executing
module code or import hooks.

The proxy cannot make variable access transparent. Document differences from
native behavior rather than adding frame inspection, bytecode rewriting, or
private runtime dependencies to hide them. Resolve relative module names when
they're declared, but consult the import system when they're used.

Use the public PEP and language/library documentation as the specification.
Don't consult existing lazy-import implementations. Small executable examples
on a native runtime can check observable behavior without reading its source.
