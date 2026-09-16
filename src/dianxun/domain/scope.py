"""Canonical scope facts and integer split invariants, without database side effects."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _batch(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Batch must be an object")
    result = {
        key: _text(row.get(key), key)
        for key in ("batch_id", "store_id", "device_id", "sku_id", "policy_ref")
    }
    quantity = row.get("quantity")
    if type(quantity) is not int or quantity < 0:
        raise ValueError("Batch quantity must be a non-negative integer")
    if row.get("lifecycle", "active") != "active":
        raise ValueError("Only active batch objects may enter the current scope")
    return {**result, "quantity": quantity, "lifecycle": "active"}


def build_scope_snapshot(
    *, tenant_id: str, store_id: str, asset_ids: list[str], batches: list[dict]
) -> dict:
    tenant_id = _text(tenant_id, "tenant_id")
    store_id = _text(store_id, "store_id")
    if not isinstance(asset_ids, list) or not asset_ids:
        raise ValueError("Scope requires asset IDs")
    assets = [_text(value, "asset_id") for value in asset_ids]
    if len(set(assets)) != len(assets):
        raise ValueError("Duplicate asset ID")
    if not isinstance(batches, list) or not batches:
        raise ValueError("Scope requires batch objects")
    normalized = [_batch(row) for row in batches]
    if len({row["batch_id"] for row in normalized}) != len(normalized):
        raise ValueError("Duplicate batch ID")
    if any(row["store_id"] != store_id for row in normalized):
        raise ValueError("Batch is outside the store scope")
    if any(row.get("tenant_id", tenant_id) != tenant_id for row in batches):
        raise ValueError("Batch is outside the tenant scope")
    return {
        "tenant_id": tenant_id,
        "store_id": store_id,
        "asset_ids": sorted(assets),
        "batches": sorted(normalized, key=lambda row: row["batch_id"]),
    }


def scope_digest(snapshot: dict) -> str:
    canonical = build_scope_snapshot(**snapshot)
    payload = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_split(parent: dict, children: list[dict]) -> list[dict]:
    """Validate one full split; DB identity/lineage/locking belong to its transaction."""
    original = _batch(parent)
    if parent.get("disposition") not in {"unknown", "quarantined"}:
        raise ValueError("Only unresolved batches may be split")
    if not isinstance(children, list) or len(children) < 2:
        raise ValueError("A split requires at least two explicit child batches")
    normalized = [_batch(row) for row in children]
    ids = [row["batch_id"] for row in normalized]
    if len(set(ids)) != len(ids) or original["batch_id"] in ids:
        raise ValueError("Child IDs must be unique and different from the parent")
    if any(row["quantity"] <= 0 for row in normalized):
        raise ValueError("Child quantities must be positive integers")
    if sum(row["quantity"] for row in normalized) != original["quantity"]:
        raise ValueError("Child quantities must conserve the parent quantity")
    for row, child in zip(normalized, children, strict=True):
        if any(
            row[key] != original[key] for key in ("store_id", "device_id", "sku_id", "policy_ref")
        ):
            raise ValueError("Split cannot change location, SKU, or policy")
        if child.get("disposition") != parent["disposition"]:
            raise ValueError("Split cannot change the disposition")
        if child.get("tenant_id") != parent.get("tenant_id"):
            raise ValueError("Split cannot change the tenant")
        if any(
            child.get(key) != parent.get(key)
            for key in ("safe_for_sale", "storage_min_c", "storage_max_c", "product_name")
        ):
            raise ValueError("Split must preserve product and safety constraints")
    return sorted(deepcopy(children), key=lambda row: row["batch_id"])
