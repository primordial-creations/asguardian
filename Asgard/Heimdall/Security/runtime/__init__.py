"""Heimdall runtime/IAST hook interface.

This package defines a documented, portable ``RuntimeObservation`` schema
and an offline ingestion + merge pipeline that lets runtime-observed
source-to-sink flows (emitted by a separate, language-specific runtime
agent -- not implemented here) confirm or extend a static ``TaintReport``.

No live instrumentation happens in this module: it is an interface plus an
offline replay loader. See ``_Docs/Asgard/Heimdall/Runtime-IAST.md`` for the
full design and epistemic framing.
"""

from Asgard.Heimdall.Security.runtime.models import (
    RuntimeConfidence,
    RuntimeObservation,
    RuntimeObservationBatch,
)
from Asgard.Heimdall.Security.runtime.ingest import (
    load_observations,
    load_observations_from_file,
    merge_runtime_observations,
)

__all__ = [
    "RuntimeConfidence",
    "RuntimeObservation",
    "RuntimeObservationBatch",
    "load_observations",
    "load_observations_from_file",
    "merge_runtime_observations",
]
