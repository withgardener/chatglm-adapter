"""Opt-in protocol drift probe.

It never runs as part of deployment automatically. The exact refresh and
conversation URLs must be supplied from a current, self-owned HAR before this
probe is allowed to call the upstream service.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from chatglm_adapter.chatglm.auth import AuthManager
from chatglm_adapter.chatglm.conversation import ConversationManager
from chatglm_adapter.chatglm.device import load_or_create_device_id
from chatglm_adapter.chatglm.headers import build_headers
from chatglm_adapter.chatglm.signer import ChatGLMSigner, TimestampProvider
from chatglm_adapter.config import Settings


async def probe(args: argparse.Namespace) -> int:
    settings = Settings(
        adapter_internal_api_key="probe-only",
        chatglm_sign_secret=args.sign_secret,
        chatglm_auth_refresh_url=args.refresh_url,
        chatglm_conversation_create_url=args.create_url,
        chatglm_conversation_delete_url=args.delete_url or "",
        chatglm_refresh_token_file=Path(args.refresh_token_file),
        chatglm_device_id_file=Path(args.device_id_file),
    )
    async with httpx.AsyncClient() as client:
        auth = AuthManager(settings, client)
        try:
            token = await auth.get_access_token()
            print("PASS auth")
        except Exception:
            print("FAIL auth")
            return 1
        device_id = load_or_create_device_id(settings.chatglm_device_id_file)
        signer = ChatGLMSigner(
            settings.chatglm_sign_secret,
            TimestampProvider(settings.chatglm_timestamp_format),
        )
        headers = build_headers(settings, signer, access_token=token, device_id=device_id)
        try:
            conversation = await ConversationManager(settings, client).create(headers)
            print("PASS conversation_create")
        except Exception:
            print("FAIL conversation_create")
            return 1
        print("PASS sign")
        if settings.chatglm_conversation_delete_url:
            await ConversationManager(settings, client).cleanup(conversation, headers)
            print("PASS conversation_cleanup")
        else:
            print("UNKNOWN conversation_cleanup")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-url", required=True)
    parser.add_argument("--create-url", required=True)
    parser.add_argument("--delete-url")
    parser.add_argument("--refresh-token-file", required=True)
    parser.add_argument("--device-id-file", required=True)
    parser.add_argument("--sign-secret", required=True)
    args = parser.parse_args()
    return asyncio.run(probe(args))


if __name__ == "__main__":
    raise SystemExit(main())

