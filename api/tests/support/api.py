"""A thin JSON client over the Flask test client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Resp:
    status: int
    json: Any
    headers: Any
    raw: Any

    @property
    def data(self):
        return (self.json or {}).get("data")

    @property
    def code(self):
        return (self.json or {}).get("code")

    def __repr__(self) -> str:
        return f"<Resp {self.status} {self.json}>"


class ApiClient:
    APP_ORIGIN = "http://localhost:5173"

    def __init__(self, client):
        self.client = client
        self.token: str | None = None

    def call(self, method: str, path: str, json: Any = None, *, token: str | None = None, if_match: int | None = None,
             headers: dict | None = None, anonymous: bool = False, raw_body: bytes | None = None,
             content_type: str = "application/json") -> Resp:
        hdrs = dict(headers or {})
        bearer = None if anonymous else (token or self.token)
        if bearer:
            hdrs["Authorization"] = f"Bearer {bearer}"
        if if_match is not None:
            hdrs["If-Match"] = f'"{if_match}"'
        kwargs: dict = {"headers": hdrs}
        if raw_body is not None:
            kwargs["data"] = raw_body
            kwargs["content_type"] = content_type
        elif json is not None:
            kwargs["json"] = json
        r = self.client.open(path, method=method, **kwargs)
        body = r.get_json(silent=True)
        return Resp(r.status_code, body, r.headers, r)

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, json=None, **kw):
        return self.call("POST", path, json, **kw)

    def put(self, path, json=None, **kw):
        return self.call("PUT", path, json, **kw)

    def patch(self, path, json=None, **kw):
        return self.call("PATCH", path, json, **kw)

    def delete(self, path, json=None, **kw):
        return self.call("DELETE", path, json, **kw)

    def csrf_headers(self) -> dict:
        return {"Origin": self.APP_ORIGIN, "X-Requested-With": "veda-workspace"}
