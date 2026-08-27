"""Deterministic seed builder for the local stateful business world."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any


def build_seed(
    *,
    anchor_time: str = "2026-08-28T09:00:00+08:00",
    random_seed: int = 42,
) -> dict[str, Any]:
    anchor = datetime.fromisoformat(anchor_time)
    rng = random.Random(random_seed)
    stores = [
        {
            "store_id": store_id,
            "tenant_id": "demo",
            "name": f"便利{store_id}号店",
            "timezone": "Asia/Shanghai",
        }
        for store_id in ("S03", "S05", "S07", "S08")
    ]
    devices = [
        {
            "device_id": f"FROST-{store_id}",
            "store_id": store_id,
            "model": "FROST-X100",
            "health_state": "normal",
            "door_state": "closed",
            "power_state": "on",
            "compressor_state": "running",
            "ambient_temp_c": 26.0,
        }
        for store_id in ("S03", "S07")
    ]
    readings: list[dict[str, Any]] = []
    for device in devices:
        # The normal baseline ends 90 minutes before the anchor. Scenarios own
        # the most recent three samples so a fault series does not conflict
        # with a synthetic normal reading at the same timestamp.
        for index, offset in enumerate(range(-180, -60, 30), start=1):
            readings.append(
                {
                    "reading_id": f"seed-{device['device_id']}-{index:02d}",
                    "device_id": device["device_id"],
                    "observed_at": (anchor + timedelta(minutes=offset)).isoformat(
                        timespec="seconds"
                    ),
                    "temp_c": round(3.5 + rng.uniform(-0.2, 0.2), 1),
                    "quality": "good",
                    "source": "seed",
                }
            )
    batches = [
        {
            "batch_id": "BATCH-S03-DAIRY-001",
            "store_id": "S03",
            "device_id": "FROST-S03",
            "sku_id": "MILK-001",
            "product_name": "巴氏鲜奶",
            "quantity": 24,
            "storage_min_c": 0.0,
            "storage_max_c": 6.0,
            "disposition": "unknown",
            "safe_for_sale": True,
            "policy_ref": "coldchain-demo:1.0.0",
        },
        {
            "batch_id": "BATCH-S03-FRESH-001",
            "store_id": "S03",
            "device_id": "FROST-S03",
            "sku_id": "SANDWICH-001",
            "product_name": "鲜食三明治",
            "quantity": 18,
            "storage_min_c": 0.0,
            "storage_max_c": 8.0,
            "disposition": "unknown",
            "safe_for_sale": True,
            "policy_ref": "coldchain-demo:1.0.0",
        },
        {
            "batch_id": "BATCH-S07-DAIRY-001",
            "store_id": "S07",
            "device_id": "FROST-S07",
            "sku_id": "YOGURT-001",
            "product_name": "低温酸奶",
            "quantity": 30,
            "storage_min_c": 0.0,
            "storage_max_c": 6.0,
            "disposition": "unknown",
            "safe_for_sale": True,
            "policy_ref": "coldchain-demo:1.0.0",
        },
    ]
    return {
        "schema_version": 1,
        "seed_id": f"dianxun-{random_seed}",
        "anchor_time": anchor.isoformat(timespec="seconds"),
        "stores": stores,
        "devices": devices,
        "device_readings": readings,
        "inventory_batches": batches,
    }
