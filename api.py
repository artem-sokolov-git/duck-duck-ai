import json
from typing import Self
from types import TracebackType
import httpx
from config import ModelType


class DuckChat:
    def __init__(
        self,
        model: ModelType = ModelType.Claude,
        client: httpx.AsyncClient = httpx.AsyncClient(),
    ) -> None:
        self._client = client
        self._model = model
        self._vqd = None

    async def __aenter__(self) -> Self:
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self._client.__aexit__(exc_type, exc_value, traceback)

    def get_headers(self):
        return {
            "Host": "duckduckgo.com",
            "Accept": "text/event-stream",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://duckduckgo.com/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "DNT": "1",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Cookie": "dcm=3; ay=b",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }

    async def simulate_browser_reqs(self) -> None:
        headers = self.get_headers()
        headers["X-Requested-With"] = "XMLHttpRequest"
        response = await self._client.get(
            "https://duckduckgo.com/country.json", headers=headers
        )
        if response.status_code != httpx.codes.OK:
            raise Exception("Can't get country json (maybe ip ban)")

    async def get_vqd(self) -> None:
        headers = self.get_headers()
        headers["Cache-Control"] = "no-store"
        headers["x-vqd-accept"] = "1"
        response = await self._client.get(
            "https://duckduckgo.com/duckchat/v1/status", headers=headers
        )
        vqd = response.headers.get("x-vqd-4")
        if vqd:
            self._vqd = vqd

    async def get_res(self, query: str) -> str:
        await self.simulate_browser_reqs()
        await self.get_vqd()
        message = []
        async with self._client.stream(
            "POST",
            "https://duckduckgo.com/duckchat/v1/chat",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
                "x-vqd-4": self._vqd,
            },
            json={
                "model": self._model.value,
                "messages": [{"role": "user", "content": query}],
            },
        ) as response:
            async for chunk in response.aiter_lines():
                chunk = chunk.replace("data: ", "").replace("\n", "").strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    obj = json.loads(chunk)
                    if type(obj) is dict and obj.get("message"):
                        message.append(obj["message"])
                except Exception:
                    print(chunk)
            new_vqd = response.headers.get("x-vqd-4")
        if not new_vqd:
            print(
                "Warn: DuckDuckGo did not return new VQD. Ignore this if everything else is ok."
            )
        else:
            self._vqd = new_vqd
        return "".join(message)