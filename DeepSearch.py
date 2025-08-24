"""
title: DeepSearch (Jina.ai)
description: A DeepSearch tool that functions similarly to ChatGPT's Deep Research, using Jina.AI DeepSearch mode.
author: Shaun (https://github.com/ayylmaonade)
repository: https://github.com/ayylmaonade/execute-bash-open-webui
date: 24/08/2025 (DD/MM/YY)
version: 0.1
license: GPLv3
"""

from pydantic import BaseModel, Field
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
import json


class Tools:
    """
    Jina DeepSearch Tool for Open-WebUI.

    - Streams results from Jina DeepSearch (SSE / newline-delimited JSON).
    - Emits status + stream events via __event_emitter__ (if provided).
    - Returns aggregated text result on completion (or an error string).
    """

    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        jina_api_key: str = Field(
            "", description="Your Jina DeepSearch API key (Bearer token)"
        )
        timeout_seconds: int = Field(
            60, description="Timeout for HTTP requests (seconds)"
        )
        reasoning_effort: str = Field(
            "low", description="Reasoning effort: low|medium|high"
        )
        budget_tokens: int = Field(500000, description="Token budget for the request")
        max_returned_urls: int = Field(
            50, description="Maximum number of returned URLs"
        )
        no_direct_answer: bool = Field(
            True, description="Ask model to avoid direct short answers"
        )
        team_size: int = Field(4, description="Team size for DeepSearch")
        stream_by_default: bool = Field(
            True, description="Whether to stream results by default"
        )

    async def deepsearch(
        self, query: str, stream: Optional[bool] = None, __event_emitter__=None
    ) -> str:
        """
        Perform a DeepSearch chat/completions request using Jina's DeepSearch API.

        Args:
            query: the user query to send as a single-user message (string)
            stream: override the valves.stream_by_default value. If True, stream results.
            __event_emitter__: optional async callable supplied by Open-WebUI for streaming events.
                              call it like: await __event_emitter__(event_dict)
        Returns:
            A string result (aggregated) or an error string. If streaming, final aggregated text is
            also returned after emission completes.
        """
        if not self.valves.jina_api_key:
            return "Error: Jina DeepSearch API key missing. Set it in tool settings."

        use_stream = (
            stream if (stream is not None) else bool(self.valves.stream_by_default)
        )

        url = "https://deepsearch.jina.ai/v1/chat/completions"
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.valves.jina_api_key}",
        }

        # Build messages: single-user prompt. You can extend to accept full chat history if desired.
        messages = [{"role": "user", "content": query}]

        payload = {
            "model": "jina-deepsearch-v1",
            "messages": messages,
            "stream": bool(use_stream),
            "reasoning_effort": self.valves.reasoning_effort,
            "budget_tokens": int(self.valves.budget_tokens),
            "max_returned_urls": str(self.valves.max_returned_urls),
            "no_direct_answer": bool(self.valves.no_direct_answer),
            "team_size": int(self.valves.team_size),
        }

        # Small helper to extract human-readable text from parsed JSON chunks (easiest).
        def _extract_text_from_parsed(obj: Any) -> Optional[str]:
            if obj is None:
                return None
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                # common shapes: {'choices':[{'delta':{'content':'...'}}]} or {'message':{'content':'...'}}
                # Try multiple plausible keys:
                for key in ("content", "text", "message", "raw"):
                    if key in obj and isinstance(obj[key], (str,)):
                        return obj[key]
                if "choices" in obj and isinstance(obj["choices"], list):
                    pieces: List[str] = []
                    for c in obj["choices"]:
                        # delta.content or message.content
                        if isinstance(c, dict):
                            if (
                                "delta" in c
                                and isinstance(c["delta"], dict)
                                and "content" in c["delta"]
                            ):
                                pieces.append(str(c["delta"]["content"]))
                            elif "message" in c and isinstance(c["message"], dict):
                                # message may have content or role+content
                                m = c["message"]
                                if "content" in m:
                                    # content might be dict or str
                                    if isinstance(m["content"], str):
                                        pieces.append(m["content"])
                                    elif (
                                        isinstance(m["content"], dict)
                                        and "text" in m["content"]
                                    ):
                                        pieces.append(str(m["content"]["text"]))
                            elif "text" in c:
                                pieces.append(str(c["text"]))
                    if pieces:
                        return "".join(pieces)
                # fallback: if dict contains any string values, concatenate a few
                string_vals = [v for v in obj.values() if isinstance(v, str)]
                if string_vals:
                    return " ".join(string_vals[:3])
            return None

        try:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "DeepSearching... May take several minutes.",
                            "done": False,
                        },
                    }
                )

            timeout = aiohttp.ClientTimeout(total=self.valves.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        # try to get body text for error handling
                        err_text = await resp.text()
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"DeepSearch API error {resp.status}",
                                        "done": True,
                                    },
                                }
                            )
                        return f"API Error {resp.status}: {err_text}"

                    # if not using streaming, return full JSON response
                    if not use_stream:
                        body = await resp.json()
                        pretty = json.dumps(body, indent=2)
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": "Received DeepSearch response.",
                                        "done": True,
                                    },
                                }
                            )
                        # return some compact text: if choices present try to extract, else full json
                        extracted = _extract_text_from_parsed(body)
                        return extracted or pretty

                    # STREAMING PATH: read chunked response and yoink parsed pieces
                    aggregated_parts: List[str] = []
                    # Many streaming endpoints deliver newline-delimited JSON or SSE-like lines.
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        try:
                            text_chunk = chunk.decode(errors="ignore")
                        except Exception:
                            text_chunk = str(chunk)

                        # split into formatted lines in case multiple json entries arrived in this chunk
                        for raw_line in text_chunk.splitlines():
                            line = raw_line.strip()
                            if not line:
                                continue
                            # SSE sometimes prefixes 'data: '
                            if line.startswith("data:"):
                                line = line[len("data:") :].strip()
                            # ignore stream end markers
                            if line in ("[DONE]", "DONE"):
                                continue
                            parsed = None
                            try:
                                parsed = json.loads(line)
                            except Exception:
                                # partial JSON or raw text; wrap as raw
                                parsed = {"raw": line}

                            # Try to extract readable text from parsed object
                            human = _extract_text_from_parsed(parsed)
                            if human:
                                aggregated_parts.append(human)
                            else:
                                # fallback: keep compact json string or the raw line
                                aggregated_parts.append(
                                    parsed.get("raw")
                                    if isinstance(parsed, dict) and "raw" in parsed
                                    else json.dumps(parsed)
                                )

                            # Emit chunk to Open-WebUI if emitter exists
                            if __event_emitter__:
                                # stream event with the parsed JSON (best-effort)
                                await __event_emitter__(
                                    {"type": "stream", "data": parsed}
                                )

                    # finished streaming
                    final_text = " ".join(p for p in aggregated_parts if p)
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": "DeepSearch complete.",
                                    "done": True,
                                },
                            }
                        )
                    return final_text or "DeepSearch returned no readable content."

        except asyncio.TimeoutError:
            return "Error: request to DeepSearch timed out."
        except Exception as e:
            # emitter for error handling
            if __event_emitter__:
                try:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Unexpected error: {str(e)}",
                                "done": True,
                            },
                        }
                    )
                except Exception:
                    pass
            return f"Unexpected error during DeepSearch: {str(e)}"
