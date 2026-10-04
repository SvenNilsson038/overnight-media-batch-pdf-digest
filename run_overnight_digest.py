"""Run one explanatory media backlog through batch summaries and PDF delivery."""

from src.infrai_digest_gateway import InfraiDigestGateway
from src.media_digest import DigestRequest, build_digest
from uuid import uuid4


sample = DigestRequest.model_validate(
    {
        "run_id": f"creator-digest-{uuid4().hex}",
        "delivery_date": "2026-09-14",
        "records": [
            {
                "asset_id": "stream-104",
                "creator_name": "Mira Chen",
                "title": "Studio tour",
                "minutes_streamed": 18420,
                "completion_rate": 0.72,
                "processing_state": "ready",
            },
            {
                "asset_id": "stream-105",
                "creator_name": "Mira Chen",
                "title": "Editing clinic",
                "minutes_streamed": 0,
                "completion_rate": 0.0,
                "processing_state": "processing",
            },
        ],
    }
)

if __name__ == "__main__":
    print(build_digest(sample, InfraiDigestGateway()).model_dump_json(indent=2))
