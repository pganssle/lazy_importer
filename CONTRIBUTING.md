# Development

Use an isolated environment with the committed dependency lock:

```sh
uv sync --locked --group test --group lint --group build --no-install-project
uv pip install --no-deps --no-build-isolation -e .
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyrefly check
uv run --no-sync zizmor --offline .github/workflows
```

`uv.lock` records the test, lint, build, release and environment-management
versions, including transitive dependencies. Runtime dependencies are empty;
consumers aren't constrained by this development lockfile. `--locked` rejects
an out-of-date lock instead of silently resolving different versions. Build
isolation is disabled after installing the locked backend, so Flit isn't
resolved independently of the lock.

Run the installed-wheel test matrix with
`uv run --locked --only-group tooling tox`. It targets Python 3.11 through
3.15, plus the 3.14 and 3.15 free-threaded builds and linting. Tox synchronizes
each environment from `uv.lock`, then installs the project as a wheel without
resolving dependencies. The free-threaded environments set `PYTHON_GIL=0` and
verify that the child interpreters have the GIL disabled. Missing interpreters
cause a failed environment; they aren't silently skipped. Select an individual
environment with `uv run --locked --only-group tooling tox -e py313`.

Tests create small packages in temporary directories and exercise the public
API in fresh processes. Shared tests run against both the fallback and native
runtime behavior. Fallback-specific tests are explicitly marked, since that
path isn't used when native lazy imports are available. Import-state tests
should stay isolated so an earlier test can't make a deferred import appear
successful by preloading its dependency.

The `run` fixture accepts a self-contained, zero-argument function or module
source. For functions, it writes the dedented function source to a temporary
script and calls it in the child process. Put imports inside the function;
parent globals, fixtures and enclosing closures aren't copied to the child.
The function keeps its normal local scope.

Use `textwrap.dedent` at the call site for multiline source strings inside
functions, methods or classes. Keep module-scope import scenarios as source:
calling a function would make its imports eager on Python 3.15 and would stop
exercising global rebinding. Star imports also require module scope. Ordinary
validation tests that don't require process isolation can run directly in
pytest.

For branch coverage, run `uv run --no-sync pytest --cov --cov-report=term-missing`.
Coverage's subprocess support captures the child interpreters. The parent test
process may report that it didn't import the package; that is expected for
these isolated tests. Native-only branches require a Python 3.15+ coverage run.

Build and validate distributions with the locked backend and release tools:

```sh
uv sync --locked --only-group build --only-group release --no-install-project
uv build --no-build-isolation
uv run --no-sync twine check --strict dist/*
```

The wheel is built from the source archive. The source archive includes tests,
and the wheel includes the license and `py.typed` marker. Keep packaging,
behavioral changes with their tests, and unrelated documentation changes in
separate commits.

## CI and releases

GitHub Actions builds the distributions, checks metadata, and tests the same
wheel on Linux, Windows and macOS with Python 3.11 through 3.15, including the
3.14 and 3.15 free-threaded builds. A separate lint job runs Ruff, pyrefly and
zizmor. Python dependencies come from `uv.lock`; Actions are pinned to full
commit IDs. Even the bootstrap uv version is read from its lockfile entry.

Dependabot checks the `uv` ecosystem monthly and groups updates to direct and
transitive dependencies, including the build tools, in one pull request. A
second monthly group updates GitHub Actions pins. Python updates are confined
to the lockfile; changing dependency bounds remains a separate decision.
To update the lock manually,
run `uv lock --upgrade`, inspect the diff, and run the locked test matrix.

To publish, update `project.version` and the lockfile, commit the change, and
publish a GitHub release with the tag `v<version>`. The release workflow checks
that the tag matches the package version and reruns CI at the release commit.
Only after every check passes does it publish the tested wheel and source
archive to PyPI. Ordinary pushes and pull requests never publish packages.

The PyPI trusted publisher must use these identifiers:

- Repository: `pganssle/lazy_importer`
- Workflow: `publish.yml`
- Environment: `pypi`

The GitHub `pypi` environment permits `v*` tags. The publishing job has only
OIDC token permissions and downloads the checked artifacts; it doesn't check
out or execute project code. No PyPI API token is required. Configuring this
workflow doesn't create a release or publish the current version.

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
