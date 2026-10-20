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

Publishing happens in two stages through `publish.yml`. After updating
`project.version` and the lockfile and committing the change, pushing a
`v<version>` tag publishes to TestPyPI. Publishing a GitHub release for that tag
then publishes to PyPI, allowing you to inspect the TestPyPI package first.
For example, after committing version `0.1.0`:

```console
git tag v0.1.0
git push origin v0.1.0
```

Both events run the locked build and test matrix at the tagged commit and check
that the tag matches the package version. The publishing job uploads the tested
wheel and source archive only after every check passes. Branch pushes and pull
requests never publish packages. A release rebuilds and tests the tagged source;
it doesn't download the earlier upload from TestPyPI.

PyPI and TestPyPI each need a trusted publisher with these identifiers:

- Repository: `pganssle/lazy_importer`
- Workflow: `publish.yml`
- Environment: `release`

For a first upload, register `lazy-importer` as a pending publisher in the
registry's account publishing settings. If the project already exists, add the
publisher in its project settings. A publisher previously configured with the
`pypi` environment needs to be updated to `release`.

The GitHub `release` environment permits `v*` tags. The publishing job has only
OIDC token permissions and downloads the checked artifacts; it doesn't check
out or execute project code. No PyPI API token is required. Configuring this
workflow doesn't create a release or publish the current version.

## Design constraints

The public surface is `lazy_importer()` and `resolve(value)`. The
fallback uses the documented import hook to create proxies and suspends
selection while executing an import. Hook lifetime is synchronized across
threads, while each thread tracks its active context depth. Each import reads
`__lazy_modules__` from the importing module's globals and checks membership;
no frame inspection or copy of the declaration is needed. Membership checks
also suspend the hook so a custom container can import its own dependencies.
Proxy locks protect publication of a resolved value, but aren't held while
executing module code or import hooks.

The proxy cannot make variable access transparent. Document differences from
native behavior rather than adding frame inspection, bytecode rewriting, or
private runtime dependencies to hide them. Resolve relative module names when
they're declared, but consult the import system when they're used.

Use the public PEP and language/library documentation as the specification.
Don't consult existing lazy-import implementations. Small executable examples
on a native runtime can check observable behavior without reading its source.
