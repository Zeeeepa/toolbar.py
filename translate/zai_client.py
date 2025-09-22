from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional

import aiohttp


class ChatCompletionResponse:
    def __init__(self, content: str, usage: Dict[str, Any] | None = None, done: bool = True):
        self.content = content
        self.usage = usage or {}
        self.done = done


class ZAIError(Exception):
    pass


class AsyncZAIClient:
    """Minimal async client focused on simple chat completions."""

    def __init__(self, base_url: str = "https://chat.z.ai", timeout: int = 120, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.verbose = verbose
        self._session: Optional[aiohttp.ClientSession] = None
        self.token: Optional[str] = None
        self._token_lock = asyncio.Lock()

        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "pragma": "no-cache",
            "referer": "https://chat.z.ai/",
            "user-agent": "Mozilla/5.0"
        }

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout, headers=self.headers)
            if not self.token:
                async with self._token_lock:
                    if not self.token:
                        await self._get_guest_token()
        return self._session

    async def _get_guest_token(self) -> None:
        session = await self.get_session()
        async with session.get(f"{self.base_url}/api/v1/auths/") as resp:
            if resp.status != 200:
                raise ZAIError(f"Failed to get guest token: {resp.status}")
            data = await resp.json()
            token = data.get("token")
            if not token:
                raise ZAIError("No token in auth response")
            self.token = token
            session.headers["authorization"] = f"Bearer {token}"

    async def simple_chat_async(self, message: str, model: str = "glm-4.5v", max_tokens: int = 2000) -> ChatCompletionResponse:
        session = await self.get_session()

        # Create a chat
        message_id = str(uuid.uuid4())
        create_payload = {
            "chat": {
                "id": "",
                "title": "Translation",
                "models": [model],
                "history": {"messages": {}, "currentId": message_id},
                "messages": [
                    {
                        "id": message_id,
                        "role": "user",
                        "content": message,
                        "timestamp": int(time.time()),
                        "models": [model],
                    }
                ],
                "enable_thinking": False,
                "timestamp": int(time.time() * 1000),
            }
        }

        async with session.post(f"{self.base_url}/api/v1/chats/new", json=create_payload) as resp:
            if resp.status != 200:
                raise ZAIError(f"Failed to create chat: {resp.status}")
            chat_data = await resp.json()
            chat_id = chat_data.get("id")
            if not chat_id:
                raise ZAIError("No chat id returned")

        # Request completion (streaming or regular)
        # We'll request non-streaming JSON lines and collect final content
        completion_payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "params": {"max_tokens": max_tokens, "temperature": 0.3},
            "chat_id": chat_id,
            "id": str(uuid.uuid4()),
        }

        session.headers["referer"] = f"https://chat.z.ai/c/{chat_id}"

        content = ""
        async with session.post(f"{self.base_url}/api/chat/completions", json=completion_payload) as resp:
            if resp.status != 200:
                raise ZAIError(f"Chat completion failed: {resp.status}")

            async for raw in resp.content:
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8").strip()
                except Exception:
                    continue
                if not line or not line.startswith("data: "):
                    continue
                payload_str = line[6:].strip()
                if not payload_str:
                    continue
                try:
                    data = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict) or "data" not in data:
                    continue
                inner = data["data"]
                if isinstance(inner, dict):
                    choices = inner.get("choices", [])
                    if choices and isinstance(choices[0], dict):
                        msg = choices[0].get("message", {})
                        if isinstance(msg, dict) and "content" in msg:
                            content = msg.get("content") or content
                    if inner.get("done"):
                        break
        return ChatCompletionResponse(content=content or "", usage={}, done=True)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class ZAIClient:
    """Sync wrapper for AsyncZAIClient."""

    def __init__(self, **kwargs):
        self._async = AsyncZAIClient(**kwargs)

    def simple_chat(self, message: str, model: str = "glm-4.5v", max_tokens: int = 2000) -> ChatCompletionResponse:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # run in new loop in executor
                import concurrent.futures

                def run_it():
                    new_loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(new_loop)
                        return new_loop.run_until_complete(self._async.simple_chat_async(message, model=model, max_tokens=max_tokens))
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    fut = ex.submit(run_it)
                    return fut.result()
        except RuntimeError:
            pass
        return asyncio.run(self._async.simple_chat_async(message, model=model, max_tokens=max_tokens))

    def close(self) -> None:
        try:
            asyncio.run(self._async.close())
        except RuntimeError:
            # already closed or loop running
            pass

