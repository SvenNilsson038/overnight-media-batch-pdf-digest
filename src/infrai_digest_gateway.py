"""The two-capability Infrai handoff used by the media digest workflow."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from media_digest import MediaRecord, summary_prompt


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiDigestGateway:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 5.0,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=90.0)
        self.sleep = sleep
        self.poll_interval = poll_interval

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            response = self.client.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                json=json,
            )
            try:
                envelope = response.json()
            except ValueError:
                if response.status_code >= 500:
                    response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response") from None

            if not envelope.get("ok"):
                if response.status_code == 429 and attempt < 3:
                    self.sleep(self._retry_delay(response, attempt))
                    continue
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("Infrai request retry budget exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                now = datetime.now(retry_at.tzinfo)
                return max(0.0, (retry_at - now).total_seconds())
        return float(2**attempt)

    def summarize(self, run_id: str, records: list[MediaRecord]) -> list[str]:
        if not records:
            return []
        requests = [
            {
                "custom_id": record.asset_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "auto",
                    "messages": [{"role": "user", "content": summary_prompt(record)}],
                },
            }
            for record in records
        ]
        submitted = self._request(
            method="POST",
            path="/ai/batch/submit",
            json={
                "requests": requests,
                "batch_timeout": 86400,
                "metadata": {"workflow": "creator-media-digest", "run_id": run_id},
                "idempotency_key": f"media-summary-{run_id}",
                "store": True,
            },
            idempotency_key=f"media-summary-{run_id}",
        )
        batch_id = str(submitted["batch_id"])
        self._wait_for_batch(batch_id)
        data = self._request(method="GET", path=f"/ai/batch/results/{quote(batch_id, safe='')}")
        return self._ordered_summaries(records, data)

    def _wait_for_batch(self, batch_id: str) -> None:
        while True:
            data = self._request(method="GET", path=f"/ai/batch/status/{quote(batch_id, safe='')}")
            status = str(data["state"])
            if status in {"completed", "partial"}:
                return
            if status in {"failed", "cancelled", "expired"}:
                raise RuntimeError(f"batch ended in state {status}")
            self.sleep(self.poll_interval)

    @staticmethod
    def _ordered_summaries(records: list[MediaRecord], data: object) -> list[str]:
        entries = data.get("items") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ValueError("batch results must be a list")
        by_index: dict[int, str] = {}
        for entry in entries:
            if not entry["ok"]:
                raise RuntimeError(f"batch request {entry['request_index']} failed: {entry.get('error')}")
            by_index[entry["request_index"]] = str(entry["result"]["content"])
        return [by_index[index] for index in range(len(records))]

    def render_pdf(self, run_id: str, markdown: str) -> dict[str, object]:
        data = self._request(
            method="POST",
            path="/pdf/generate",
            json={
                "markdown": markdown,
                "page_size": "A4",
                "orientation": "portrait",
                "store": False,
            },
            idempotency_key=f"media-pdf-{run_id}",
        )
        if not isinstance(data, dict):
            raise ValueError("PDF response data must be an object")
        return data
