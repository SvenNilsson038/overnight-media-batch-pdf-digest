"""Domain decisions and orchestration for a creator's overnight media digest."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Protocol

from pydantic import BaseModel, Field


class MediaRecord(BaseModel):
    asset_id: str = Field(min_length=1)
    creator_name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    minutes_streamed: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    processing_state: str = Field(pattern="^(ready|processing|failed)$")


class DigestRequest(BaseModel):
    run_id: str = Field(min_length=1)
    delivery_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    records: list[MediaRecord] = Field(min_length=1)


class DigestDelivery(BaseModel):
    run_id: str
    included_assets: list[str]
    pdf: dict[str, object]


class DigestGateway(Protocol):
    def summarize(self, run_id: str, records: list[MediaRecord]) -> list[str]: ...

    def render_pdf(self, run_id: str, markdown: str) -> dict[str, object]: ...


def records_ready_for_digest(records: list[MediaRecord]) -> list[MediaRecord]:
    """Only processed assets with actual viewing belong in the creator digest."""
    return [
        record
        for record in records
        if record.processing_state == "ready" and record.minutes_streamed > 0
    ]


def summary_prompt(record: MediaRecord) -> str:
    return (
        "Summarize this media performance record for its creator in two factual "
        "sentences. Mention viewing time and completion rate; do not invent causes.\n"
        f"Asset: {record.asset_id}\nTitle: {record.title}\n"
        f"Minutes streamed: {record.minutes_streamed}\n"
        f"Completion rate: {record.completion_rate:.0%}"
    )


def digest_markdown(request: DigestRequest, records: list[MediaRecord], summaries: list[str]) -> str:
    if len(records) != len(summaries):
        raise ValueError("each included media record must have one summary")
    rows = [
        f"## {escape(record.title)}\n\n{escape(summary)}"
        for record, summary in zip(records, summaries, strict=True)
    ]
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n\n".join(
        [
            f"# Creator media digest: {request.delivery_date}",
            f"Generated {generated_at}; {len(records)} ready assets with viewing activity.",
            *rows,
        ]
    )


def build_digest(request: DigestRequest, gateway: DigestGateway) -> DigestDelivery:
    selected = records_ready_for_digest(request.records)
    summaries = gateway.summarize(request.run_id, selected)
    markdown = digest_markdown(request, selected, summaries)
    pdf = gateway.render_pdf(request.run_id, markdown)
    return DigestDelivery(
        run_id=request.run_id,
        included_assets=[record.asset_id for record in selected],
        pdf=pdf,
    )

