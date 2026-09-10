"""Create a reviewable HAR fixture without credentials or user content.

This intentionally keeps only protocol shape and safe metadata. It is not a
forensic sanitizer for arbitrary HAR files; inspect the output before commit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SECRET_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-device-id",
    "x-request-id",
}
SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "uid",
    "user_id",
    "device_id",
    "conversation_id",
    "request_id",
}
CONTENT_KEYS = {"prompt", "completion", "text", "content", "responsetext"}


def sanitize(value: Any, *, key: str | None = None) -> Any:
    lowered = key.lower() if key else ""
    if lowered in SECRET_KEYS:
        return f"<{lowered.upper()}>"
    if lowered in CONTENT_KEYS and isinstance(value, str):
        return "<TEXT>"
    if isinstance(value, dict):
        return {k: sanitize(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, key=key) for v in value]
    return value


def sanitize_headers(headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for header in headers:
        name = str(header.get("name", ""))
        if name.lower() in SECRET_HEADERS:
            result.append({"name": name, "value": "<REDACTED>"})
        else:
            result.append({"name": name, "value": "<PRESENT>"})
    return result


def sanitize_har(document: dict[str, Any]) -> dict[str, Any]:
    log = document.get("log", {})
    entries = []
    for entry in log.get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})
        entries.append(
            {
                "startedDateTime": entry.get("startedDateTime", "<TIME>"),
                "time": entry.get("time", 0),
                "request": {
                    "method": request.get("method", ""),
                    "url": _safe_url(request.get("url", "")),
                    "httpVersion": request.get("httpVersion", ""),
                    "headers": sanitize_headers(request.get("headers", [])),
                    "postData": _safe_post_data(request.get("postData")),
                },
                "response": {
                    "status": response.get("status", 0),
                    "statusText": response.get("statusText", ""),
                    "headers": sanitize_headers(response.get("headers", [])),
                    "content": {
                        "mimeType": response.get("content", {}).get("mimeType", ""),
                        "size": response.get("content", {}).get("size", 0),
                    },
                },
            }
        )
    return {"log": {"version": log.get("version", "1.2"), "creator": {"name": "sanitized"}, "entries": entries}}


def _safe_url(url: str) -> str:
    if not isinstance(url, str):
        return ""
    return url.split("?", 1)[0]


def _safe_post_data(post_data: Any) -> Any:
    if not isinstance(post_data, dict):
        return None
    result = {"mimeType": post_data.get("mimeType", "application/json")}
    text = post_data.get("text")
    if text:
        try:
            result["text"] = sanitize(json.loads(text))
        except (TypeError, json.JSONDecodeError):
            result["text"] = "<BODY>"
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: sanitize_har.py INPUT.har OUTPUT.har", file=sys.stderr)
        return 2
    source, destination = map(Path, sys.argv[1:])
    with source.open("r", encoding="utf-8") as handle:
        sanitized = sanitize_har(json.load(handle))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(sanitized, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

