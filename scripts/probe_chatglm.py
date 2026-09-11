"""Opt-in protocol drift probe for a self-owned ChatGLM Web account."""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import httpx

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.client import ChatGLMClient
from chatglm_adapter.chatglm.conversation import ConversationManager
from chatglm_adapter.chatglm.cookies import CookieStore
from chatglm_adapter.chatglm.device import resolve_device_id
from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.chatglm.sse_parser import StreamNormalizer
from chatglm_adapter.config import Settings
from chatglm_adapter.core.events import ReasoningDelta, TextDelta, Unknown
from chatglm_adapter.openai.schemas import ChatCompletionRequest


async def probe(args: argparse.Namespace) -> int:
    cookies_file = Path(args.cookies_file) if args.cookies_file else None
    settings = Settings(
        adapter_internal_api_key="probe-only",
        chatglm_sign_secret=args.sign_secret,
        chatglm_auth_refresh_url=args.refresh_url,
        chatglm_conversation_create_url=args.create_url,
        chatglm_conversation_delete_url=args.delete_url,
        chatglm_stream_url=args.stream_url,
        chatglm_time_sync_url=args.time_sync_url,
        chatglm_refresh_token_file=Path(args.refresh_token_file)
        if args.refresh_token_file
        else Path("/nonexistent"),
        chatglm_cookies_file=cookies_file,
        chatglm_device_id_file=Path(args.device_id_file),
    )
    cookies = CookieStore.load(cookies_file) if cookies_file else None
    device_id = resolve_device_id(settings, cookies.refresh_token if cookies else None)
    signer = ChatGLMSigner(
        settings.chatglm_sign_secret,
        TimestampProvider(settings.chatglm_timestamp_format),
    )
    async with httpx.AsyncClient() as client:
        auth = AuthManager(settings, client, signer, device_id, cookies)
        try:
            await auth.get_access_token()
            print("PASS auth")
        except Exception:
            print("FAIL auth")
            return 1
        print("PASS sign")
        print("PASS conversation_init")
        request = ChatCompletionRequest(
            model="chatglm-glm-5.3-flash",
            messages=[{"role": "user", "content": args.prompt}],
            stream=True,
        )
        chatglm = ChatGLMClient(
            settings,
            client,
            auth,
            signer,
            device_id,
            ConversationManager(settings, client),
        )
        try:
            event_count = 0
            counts: dict[str, int] = {}
            text_chars = 0
            reasoning_chars = 0
            first_event_ms: float | None = None
            last_event_ms = 0.0
            text_arrivals: list[float] = []
            normalizer = StreamNormalizer()
            started = time.perf_counter()
            async for raw in chatglm.stream(
                request,
                ChatGLMRequestBuilder(
                    settings.chatglm_model_glm_5_3_flash,
                    settings.chatglm_assistant_id,
                ),
                request_id="protocol-probe",
            ):
                event_count += 1
                elapsed_ms = (time.perf_counter() - started) * 1000
                if first_event_ms is None:
                    first_event_ms = elapsed_ms
                last_event_ms = elapsed_ms
                for event in normalizer.normalize(raw):
                    if isinstance(event, Unknown):
                        # Shapes carry field names and type markers only.
                        print(f"UNKNOWN event={event.event} shape={event.payload_shape}")
                        continue
                    name = type(event).__name__
                    counts[name] = counts.get(name, 0) + 1
                    if isinstance(event, TextDelta):
                        text_chars += len(event.text)
                        text_arrivals.append(elapsed_ms)
                    elif isinstance(event, ReasoningDelta):
                        reasoning_chars += len(event.text)
            print(f"event summary: {counts or 'no normalized events'}")
            print(f"text_chars={text_chars} reasoning_chars={reasoning_chars}")
            if first_event_ms is not None:
                print(f"first_event_ms={first_event_ms:.0f} last_event_ms={last_event_ms:.0f}")
            if text_arrivals:
                gaps = [
                    round(b - a) for a, b in zip(text_arrivals, text_arrivals[1:], strict=True)
                ]
                print(
                    f"text_deltas={len(text_arrivals)} "
                    f"first_text_ms={text_arrivals[0]:.0f} "
                    f"delta_gap_ms min={min(gaps) if gaps else 0} "
                    f"max={max(gaps) if gaps else 0}"
                )
            if not event_count:
                print("FAIL stream")
                return 1
            if not counts.get("TextDelta"):
                print("FAIL stream (no text deltas)")
                return 1
            print("PASS stream")
            print("PASS sse")
            print("PASS conversation_cleanup")
        except Exception:
            print("FAIL stream")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-url",
        default="https://chatglm.cn/chatglm/user-api/user/refresh",
    )
    parser.add_argument("--create-url", default="")
    parser.add_argument(
        "--delete-url",
        default="https://chatglm.cn/chatglm/mainchat-api/conversation/delete",
    )
    parser.add_argument(
        "--stream-url",
        default="https://chatglm.cn/chatglm/backend-api/assistant/stream",
    )
    parser.add_argument(
        "--time-sync-url",
        default="https://chatglm.cn/chatglm/operation-api/config/cur_ts",
    )
    parser.add_argument("--refresh-token-file", default="")
    parser.add_argument("--cookies-file", default="")
    parser.add_argument("--device-id-file", required=True)
    parser.add_argument("--sign-secret", required=True)
    parser.add_argument("--prompt", default="请只回答：OK")
    args = parser.parse_args()
    return asyncio.run(probe(args))


if __name__ == "__main__":
    raise SystemExit(main())
