#!/usr/bin/env python3
"""Sprint 7.3 — simulate N concurrent call sessions against the Order API."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESTAURANT = "hot_bagels_2nd_street"
DEFAULT_BASE = os.environ.get("ORDER_API_BASE_URL", "http://127.0.0.1:8000")


async def _one_call(client: httpx.AsyncClient, index: int) -> tuple[int, float, str | None]:
    call_id = f"load-{index}-{uuid.uuid4().hex[:8]}"
    base = f"/v1/restaurants/{RESTAURANT}/calls/{call_id}"
    started = time.perf_counter()
    try:
        r = await client.post(f"{base}/reset")
        if r.status_code != 200:
            return index, time.perf_counter() - started, f"reset failed: {r.status_code}"
        r = await client.post(
            f"{base}/tools/add_item",
            json={"item_term": "cream cheese sandwich"},
        )
        if r.status_code != 200:
            return index, time.perf_counter() - started, f"add_item failed: {r.status_code}"
        body = r.json()
        if body.get("status") != "success":
            return index, time.perf_counter() - started, f"add_item status={body.get('status')}"
        r = await client.get(f"{base}/cart")
        if r.status_code != 200:
            return index, time.perf_counter() - started, f"cart failed: {r.status_code}"
        return index, time.perf_counter() - started, None
    except Exception as exc:
        return index, time.perf_counter() - started, str(exc)


async def run_load_test(base_url: str, concurrency: int) -> int:
    print(f"Load test: {concurrency} concurrent calls -> {base_url}")
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            health = await client.get("/health")
            health.raise_for_status()
        except Exception as exc:
            print(f"Order API not reachable: {exc}")
            return 1

        started = time.perf_counter()
        results = await asyncio.gather(*[_one_call(client, i) for i in range(concurrency)])
        elapsed = time.perf_counter() - started

    failures = [(idx, err) for idx, _dur, err in results if err]
    for idx, dur, err in sorted(results):
        mark = "OK" if err is None else "FAIL"
        print(f"  [{mark}] call {idx}: {dur * 1000:.0f}ms" + (f" — {err}" if err else ""))

    print(f"\n{concurrency - len(failures)}/{concurrency} succeeded in {elapsed:.2f}s")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Concurrent call load test")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    return asyncio.run(run_load_test(args.base_url, args.concurrency))


if __name__ == "__main__":
    raise SystemExit(main())
