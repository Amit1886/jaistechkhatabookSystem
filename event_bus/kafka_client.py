from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _bootstrap_servers() -> str:
    return (os.getenv("KAFKA_BOOTSTRAP_SERVERS") or os.getenv("KAFKA_BROKERS") or "redpanda:9092").strip()


def is_kafka_enabled() -> bool:
    v = (os.getenv("KAFKA_ENABLED") or "").strip().lower()
    # Default OFF for local installs to avoid noisy errors.
    return v in {"1", "true", "yes", "on"}


def send_kafka_message(*, topic: str, key: str, payload: dict[str, Any]) -> tuple[bool, str]:
    """
    Best-effort Kafka producer (optional dependency: kafka-python).
    """
    if not is_kafka_enabled():
        return False, "kafka_disabled"

    try:
        from kafka import KafkaProducer  # type: ignore
    except Exception:
        return False, "kafka-python not installed"

    try:
        producer = KafkaProducer(
            bootstrap_servers=_bootstrap_servers(),
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda v: (v or "").encode("utf-8"),
            acks="all",
            retries=2,
            linger_ms=20,
        )
        future = producer.send(topic, key=key or "", value=payload or {})
        future.get(timeout=10)
        producer.flush(timeout=10)
        try:
            producer.close(timeout=5)
        except Exception:
            pass
        return True, ""
    except Exception as e:
        logger.exception("Kafka send failed")
        return False, f"{type(e).__name__}: {e}"
