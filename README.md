# lazy-importer

A pure-Python compatibility context for opt-in lazy imports, inspired by
[this proposal](https://discuss.python.org/t/pep-810-explicit-lazy-imports/104131/176).
Requires Python 3.13 or later. Licensed under Apache 2.0.

The project targets the public semantics of
[PEP 810](https://peps.python.org/pep-0810/), without using CPython internals or
consulting existing lazy-import implementations.
