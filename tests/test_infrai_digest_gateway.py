import httpx

from infrai_digest_gateway import InfraiDigestGateway
from media_digest import MediaRecord


def test_live_batch_response_fields_and_order() -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/submit"):
            return httpx.Response(200, json={"ok": True, "data": {"batch_id": "batch-1", "state": "queued"}})
        if request.url.path.endswith("/status/batch-1"):
            return httpx.Response(200, json={"ok": True, "data": {"batch_id": "batch-1", "state": "completed"}})
        return httpx.Response(200, json={"ok": True, "data": {"items": [
            {"request_index": 1, "ok": True, "result": {"content": "second"}},
            {"request_index": 0, "ok": True, "result": {"content": "first"}},
        ]}})

    gateway = InfraiDigestGateway(api_key="test", client=httpx.Client(transport=httpx.MockTransport(respond)))
    records = [MediaRecord(asset_id=name, creator_name="Mira", title=name, minutes_streamed=1,
                           completion_rate=0.5, processing_state="ready") for name in ("a", "b")]

    assert gateway.summarize("run-1", records) == ["first", "second"]
    assert [call.url.path for call in calls] == [
        "/v1/ai/batch/submit", "/v1/ai/batch/status/batch-1", "/v1/ai/batch/results/batch-1"
    ]


def test_batch_item_error_is_not_rendered_as_summary() -> None:
    try:
        InfraiDigestGateway._ordered_summaries([], {"items": [
            {"request_index": 0, "ok": False, "error": {"code": "FAILED"}}
        ]})
    except RuntimeError as exc:
        assert "FAILED" in str(exc)
    else:
        raise AssertionError("failed batch item was accepted")
