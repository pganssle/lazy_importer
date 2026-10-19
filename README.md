# lazy-importer

A pure-Python compatibility context for opt-in lazy imports, inspired by
[this proposal](https://discuss.python.org/t/pep-810-explicit-lazy-imports/104131/176).
Requires Python 3.11 or later. Licensed under Apache 2.0.

The project targets the public semantics of
[PEP 810](https://peps.python.org/pep-0810/), without using CPython internals or
consulting existing lazy-import implementations.

## Usage

Install from a checkout with `python -m pip install .`:

```python
from lazy_importer import lazy_importer

__lazy_modules__ = {"json", "pathlib"}

with lazy_importer(__lazy_modules__):
    import json
    from pathlib import Path


# Importing this module doesn't load json or pathlib for these statements.
def read_config(filename: str) -> object:
    return json.loads(Path(filename).read_text(encoding="utf-8"))
```

Keep the `__lazy_modules__` declaration: Python 3.15+ uses it directly, and the
context becomes a no-op when the runtime exposes `builtins.__lazy_import__`.
Native mode respects the interpreter's lazy-import controls and filtering.
Without the declaration, the context alone won't enable native laziness.

On older runtimes, the context defers imports whose **fully qualified names
match exactly**. Selecting `example` doesn't select `example.child`.
For relative imports, select the absolute name: `from .child import value`
inside `example` requires `"example.child"`, while `from . import child`
requires `"example"`. Names are validated and copied when creating the context.

Use a fresh context for each block and keep the block at module scope,
containing only import statements. Nested fallback contexts use the innermost
selection; an empty selection makes imports eager within that block.

## Resolution and errors

The fallback binds proxies without searching for or executing the selected
modules. Attribute access, calls and supported Python protocols resolve them.
`from` imports resolve each requested name independently, so using one name
doesn't freeze the values of the others. Star imports stay eager.

The real import uses the import hooks and search path in effect at resolution
time. Dependencies execute normally; laziness doesn't cascade through the
import graph. Resolved modules enter `sys.modules` through the ordinary import
machinery. Import exceptions propagate at use time, and a failed resolution can
be retried. Successful resolutions are cached, including values such as `None`.

Use `resolve()` when passing an imported object to code that requires its real
identity or type:

```python
from lazy_importer import lazy_importer, resolve

__lazy_modules__ = {"decimal"}
with lazy_importer(__lazy_modules__):
    from decimal import Decimal

amount = resolve(Decimal)("12.50")
assert isinstance(amount, resolve(Decimal))
```

`resolve(value)` returns ordinary objects unchanged. On the fallback, it also
replaces matching bindings in the importing module's globals, preserving names
that have since been reassigned. References stored elsewhere still point to the
proxy, which keeps its resolved value.

## Compatibility limits

This is a best-effort compatibility layer, not a backport of the interpreter.
The fallback cannot intercept ordinary variable reads without relying on
interpreter internals or transforming user code. In particular:

- Assigning a proxy to another variable or placing it in a container doesn't
  resolve it. `is` and `type()` can observe the proxy. Use `resolve()` before
  identity checks, exception matching, serialization, or calls into extensions
  that require concrete objects. An eager function receiving a proxy may also
  need explicit resolution at the call site.
- Retrieving an importing module's attribute doesn't itself resolve its proxy.
  A subsequent operation generally does. Supported operations include calls,
  arithmetic, comparisons, iteration, indexing, context management and use as a
  class base; arbitrary object protocols aren't guaranteed transparent.
- Protocol inspection can see methods supplied by the proxy even when the
  eventual object doesn't support them. Fallback `repr()` resolves the object.
- The fallback doesn't implement `sys.lazy_modules`, native import filtering,
  or native declaration-site exception chaining. It doesn't enforce Python's
  syntax restrictions on lazy imports inside functions, classes or `try`
  blocks. Keep contexts around module-level import statements for portable code.
- A fallback context affects imports made by code called within the block on
  the same thread. Don't yield or await while the context is active: tasks on
  that thread would share its selection. Other threads have independent
  selections, and overlapping contexts restore the hook when the last exits.

The fallback temporarily replaces `builtins.__import__`, preserving a
pre-existing hook. Avoid changing that hook concurrently with active contexts.
If another component replaces it during a block, exiting won't overwrite that
replacement. No proxy is inserted into `sys.modules`, and no frame inspection,
bytecode manipulation or private interpreter API is used.

The package has no runtime dependencies. See [CONTRIBUTING.md](CONTRIBUTING.md)
for testing and build instructions.
