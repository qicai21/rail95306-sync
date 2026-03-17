import time
from pathlib import Path
from typing import Any

from .pipeline import ShipmentCollectionSpec, run_shipment_collection


DEFAULT_COLLECTION_INTERVAL_SECONDS = 20 * 60


def run_collection_scheduler(
    spec: ShipmentCollectionSpec,
    *,
    db_path: Path | None = None,
    interval_seconds: int = DEFAULT_COLLECTION_INTERVAL_SECONDS,
) -> int:
    while True:
        result: dict[str, Any] = run_shipment_collection(spec, db_path=db_path)
        print(result)
        time.sleep(interval_seconds)
