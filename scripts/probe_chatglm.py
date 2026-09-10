"""Opt-in protocol drift probe for a self-owned ChatGLM Web account."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.client import ChatGLMClient
from chatglm_adapter.chatglm.conversation import ConversationManager
from chatglm_adapter.chatglm.device import load_or_create_device_id
from chatglm_adapter.chatglm.request_builder import ChatGLMRequestBuilder
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.config import Settings
from chatglm_adapter.openai.schemas import ChatCompletionRequest


async def probe(args: argparse.Namespace) -> int:
    settings = Settings(
        adapter_internal_api_key="probe-only",
        chatglm_sign_secret=args.sign_secret,
        chatglm_auth_refresh_url=args.refresh_url,
        chatglm_conversation_create_url=args.create_url,
        chatglm_conversation_delete_url=args.delete_url,
        chatglm_stream_url=args.stream_url,
        chatglm_time_sync_url=args.time_sync_url,
        chatglm_refresh_token_file=Path(args.refresh_token_file),
        chatglm_device_id_file=Path(args.device_id_file),
    )
    device_id = load_or_create_device_id(settings.chatglm_device_id_file)
    signer = ChatGLMSigner(
        settings.chatglm_sign_secret,
        TimestampProvider(settings.chatglm_timestamp_format),
    )
    async with httpx.AsyncClient() as client:
        auth = AuthManager(settings, client, signer, device_id)
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
            async for raw in chatglm.stream(
                request,
                ChatGLMRequestBuilder(settings.chatglm_model_glm_5_3_flash, settings.chatglm_assistant_id),
                request_id="protocol-probe",
            ):
                event_count += 1
            if not event_count:
                print("FAIL stream")
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
    parser.add_argument("--refresh-token-file", required=True)
    parser.add_argument("--device-id-file", required=True)
    parser.add_argument("--sign-secret", required=True)
    parser.add_argument("--prompt", default="请只回答：OK")
    args = parser.parse_args()
    return asyncio.run(probe(args))


if __name__ == "__main__":
    raise SystemExit(main())
