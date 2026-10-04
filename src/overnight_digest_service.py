"""HTTP service boundary for an overnight media backlog."""

from fastapi import FastAPI, HTTPException

from infrai_digest_gateway import InfraiDigestGateway, InfraiError
from media_digest import DigestDelivery, DigestRequest, build_digest


app = FastAPI(title="Overnight creator media digest")


@app.post("/digests", response_model=DigestDelivery)
def create_digest(request: DigestRequest) -> DigestDelivery:
    try:
        return build_digest(request, InfraiDigestGateway())
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "error": exc.detail}) from exc

