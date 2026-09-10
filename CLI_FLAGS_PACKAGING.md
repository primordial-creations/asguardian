# Shared owner CLI flags

`Asgard.common.cli_flags.add_performance_flags` is the sole maintained definition
of Forseti/Volundr's parallel, worker, incremental, cache and baseline arguments.
Both real parser families import it directly. Their former private helper modules
re-export the same function object for compatibility.

Retain these aliases throughout the current engine major version. Remove them in
the next major only after an import inventory confirms no supported external
caller still uses the private path. Rollback pin: engine source `0ebe16f3`.
No scanner rules, defaults, help text or command execution policy changed.

Validated against the prior implementation: default and explicit argument values,
help output, alias identity, both real parser factories, and 59 existing Volundr
CLI tests. This source cleanup does not qualify a new engine artifact or close
broader SDK profile, distribution or consumer migration gates.
