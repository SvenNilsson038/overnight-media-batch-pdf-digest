from media_digest import DigestRequest, build_digest


class RecordingGateway:
    def __init__(self) -> None:
        self.summarized_assets: list[str] = []
        self.rendered_markdown = ""

    def summarize(self, run_id: str, records: list[object]) -> list[str]:
        self.summarized_assets = [record.asset_id for record in records]  # type: ignore[attr-defined]
        return [f"Summary for {asset_id}" for asset_id in self.summarized_assets]

    def render_pdf(self, run_id: str, markdown: str) -> dict[str, object]:
        self.rendered_markdown = markdown
        return {"pdf_id": "pdf_digest_42", "page_count": 1}


def test_only_ready_watched_assets_cross_the_batch_to_pdf_handoff() -> None:
    request = DigestRequest.model_validate(
        {
            "run_id": "night-42",
            "delivery_date": "2026-09-14",
            "records": [
                {
                    "asset_id": "ready-watched",
                    "creator_name": "Mira",
                    "title": "Live set",
                    "minutes_streamed": 900,
                    "completion_rate": 0.8,
                    "processing_state": "ready",
                },
                {
                    "asset_id": "still-processing",
                    "creator_name": "Mira",
                    "title": "Rough cut",
                    "minutes_streamed": 400,
                    "completion_rate": 0.4,
                    "processing_state": "processing",
                },
                {
                    "asset_id": "ready-unwatched",
                    "creator_name": "Mira",
                    "title": "Trailer",
                    "minutes_streamed": 0,
                    "completion_rate": 0.0,
                    "processing_state": "ready",
                },
            ],
        }
    )
    gateway = RecordingGateway()

    delivery = build_digest(request, gateway)

    assert gateway.summarized_assets == ["ready-watched"]
    assert delivery.included_assets == ["ready-watched"]
    assert "Summary for ready-watched" in gateway.rendered_markdown
    assert "Rough cut" not in gateway.rendered_markdown

