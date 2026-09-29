"""Metrics (LOG-006, 02 §9; IR-12).

Metrics are structured log lines in CloudWatch Embedded Metric Format (EMF): the CloudWatch agent turns each
line into metric data points, so no separate metrics client or network call runs in the request path. The
alarm definitions that consume them are listed in docs/operations/api-runbooks.md (alert routing and the
RG-5 test-fire are deployment steps).

    metrics.emit("OutboxDead", 1, dimensions={"Service": "worker"})
"""

from __future__ import annotations

import logging
import time
from typing import Any

NAMESPACE = "Veda/API"
UNITS = {"Count", "Milliseconds", "Seconds", "Percent", "Bytes", "None"}

log = logging.getLogger("veda.metrics")


def emf(metrics: dict[str, tuple[float, str]], dimensions: dict[str, str] | None = None) -> dict[str, Any]:
    """The EMF document for one or more metrics sharing a dimension set."""
    dims = {k: str(v)[:200] for k, v in (dimensions or {}).items()}
    for _, unit in metrics.values():
        if unit not in UNITS:
            raise ValueError(f"unknown metric unit {unit}")
    return {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [sorted(dims)] if dims else [[]],
                    "Metrics": [{"Name": name, "Unit": unit} for name, (_, unit) in metrics.items()],
                }
            ],
        },
        **dims,
        **{name: value for name, (value, _) in metrics.items()},
    }


def emit(name: str, value: float = 1, unit: str = "Count", *, dimensions: dict[str, str] | None = None) -> None:
    emit_many({name: (value, unit)}, dimensions=dimensions)


def emit_many(metrics: dict[str, tuple[float, str]], *, dimensions: dict[str, str] | None = None) -> None:
    try:
        log.info("metric", extra={"emf": emf(metrics, dimensions)})
    except Exception:  # pragma: no cover - metrics never break the caller
        log.debug("metric_emit_failed", exc_info=True)
