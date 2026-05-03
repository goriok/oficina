#!/usr/bin/env python3
"""Push token-tracker metrics to a Prometheus Pushgateway.

Collects metrics from the token-tracker exporter (OpenCode + Claude Code data),
clears stale labels, and pushes them to a remote Pushgateway via the
``prometheus_client.push_to_gateway`` API.

Usage::

    python pusher.py --gateway http://pushgateway.monitoring.svc.cluster.local:9091

    # Or via kubectl port-forward:
    #   kubectl port-forward -n monitoring svc/pushgateway 9091:9091 &
    #   python pusher.py --gateway http://localhost:9091
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Append the token-tracker root so we can import the exporter module.
_TOKEN_TRACKER_DIR = os.path.expanduser("~/.config/opencode/token_tracker")
sys.path.insert(0, _TOKEN_TRACKER_DIR)

from prometheus_client import CollectorRegistry, push_to_gateway, Gauge

# Re-use the exporter's Gauge definitions (labels, names) and collect_metrics().
from exporter import (
    collect_metrics,
    cost_tracked_total,
    tokens_total,
    cost_estimated_total,
    messages_total,
)

logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(description="Push token-tracker metrics to Pushgateway")
    parser.add_argument(
        "--gateway",
        default=os.getenv("PUSHGATEWAY_URL", "http://localhost:9091"),
        help="Pushgateway URL (env: PUSHGATEWAY_URL)",
    )
    parser.add_argument(
        "--job",
        default="token-tracker",
        help="Job label for Pushgateway grouping (default: token-tracker)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of history to query (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Collect into a fresh registry so we don't carry stale state between runs.
    registry = CollectorRegistry()
    collect_metrics(days=args.days)

    # Register the exporter's gauges under the fresh registry.
    registry.register(tokens_total)
    registry.register(cost_tracked_total)
    registry.register(cost_estimated_total)
    registry.register(messages_total)

    logger.info("Pushing %d metrics to %s (job=%s)", 4, args.gateway, args.job)

    try:
        push_to_gateway(
            gateway=args.gateway,
            job=args.job,
            registry=registry,
            timeout=10,
        )
        logger.info("Push successful")
    except Exception as exc:
        logger.error("Push failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
