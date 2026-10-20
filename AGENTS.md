# Project guidance

Read README.md for the public API and compatibility limits, and CONTRIBUTING.md
for design constraints, environment setup, tests, and release procedures.

The public surface is `lazy_importer()` and `resolve(value)`. Preserve native
runtime delegation and keep fallback limitations explicit. Use documented
Python protocols; don't add frame inspection, bytecode rewriting, or private
runtime dependencies to hide differences from native lazy imports.

Use the public PEP and language/library documentation as the specification.
Don't consult existing lazy-import implementations. Native-runtime experiments
may check observable behavior without reading implementation source.

Keep import-state tests isolated in fresh processes using the existing `run`
fixture. Keep module-level import scenarios as source strings, since wrapping
them in functions changes native lazy-import behavior. Run the relevant tests
and static checks described in CONTRIBUTING.md for each change.

Use the committed dependency lock. Keep packaging changes, behavioral changes
with their tests, and unrelated documentation changes in separate commits.
