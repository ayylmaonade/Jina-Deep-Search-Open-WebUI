from pydantic import BaseModel, Field
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
import json


class Tools:
    """
    Jina DeepSearch Tool for Open-WebUI - Now properly frames queries from the correct perspective.
    - Streams results from Jina DeepSearch (SSE / newline-delimited JSON).
    - Emits status + stream events via __event_emitter__ (if provided).
    - Returns aggregated text result on completion (or an error string).
    - Added a system prompt to instruct model to act as research assistant (works well in testing at least)
    - Sorted the wrong descriptions for some parameters (I misunderstood Jina, sue me.)
    - Increased timeout default to 600 seconds as 60 by default would always time out.
    - If you're reading this, at least somebody cares about comments. Shoutout you.
    """

    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        jina_api_key: str = Field(
            "", description="Your Jina DeepSearch API key (Bearer token)"
        )
        timeout_seconds: int = Field(
            600, description="Timeout for HTTP requests (seconds)"
        )
        reasoning_effort: str = Field(
            "low", description="Reasoning effort: low|medium|high"
        )
        budget_tokens: int = Field(500000, description="Token budget for the request. Overrides reasoning effort.")
        max_returned_urls: int = Field(
            50,
            description="Number of returned URLs that will be considered in the request and answer",
        )
        no_direct_answer: bool = Field(
            True, description="Ask model to avoid direct short answers"
        )
        team_size: int = Field(4, description="Team size for DeepSearch")
        stream_by_default: bool = Field(
            True, description="Whether to stream results by default (buggy in OWI)"
        )

    async def deepsearch(
        self, query: str, stream: Optional[bool] = None, __event_emitter__=None
    ) -> str:
        """
        The sys prompt I was on about above: (line 14)
        The external model now receives:
          SYSTEM: "You are a research assistant conducting deep search..."
          USER: "Research request: [original query]"
        This ensures the model generates search results instead of direct answers.
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

        # System prompt explicitly instructs model to act as researcher
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant conducting deep searches. "
                    "Your task is to find comprehensive, authoritative information on the topic. "
                    "Structure results as: Key Findings, Verified Sources (with URLs), and Analysis. "
                    "NEVER provide direct answers - only present search results and sources."
                ),
            },
            {"role": "user", "content": f"Research request: {query}"},
        ]

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

        # Small helper function to extract human-readable text from parsed JSON chunks
        def _extract_text_from_parsed(obj: Any) -> Optional[str]:
            if obj is None:
                return None
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                # note to self: common shapes: {'choices':[{'delta':{'content':'...'}}]} or {'message':{'content':'...'}}
                # Try multiple plausible keys in case of fuckery:
                for key in ("content", "text", "message", "raw"):
                    if key in obj and isinstance(obj[key], (str,)):
                        return obj[key]
                if "choices" in obj and isinstance(obj["choices"], list):
                    pieces: List[str] = []
                    for c in obj["choices"]:
                        # delta.content or message.content? we account for both
                        if isinstance(c, dict):
                            if (
                                "delta" in c
                                and isinstance(c["delta"], dict)
                                and "content" in c["delta"]
                            ):
                                pieces.append(str(c["delta"]["content"]))
                            elif "message" in c and isinstance(c["message"], dict):
                                # message may have content or role+content, dealt with
                                m = c["message"]
                                if "content" in m:
                                    # content might be dict or str, so we deal with it here
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
                # fallback: if dict contains any string values, concatenate a few the ol' fashioned way
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
                            "description": "DeepSearching...",
                            "done": False,
                        },
                    }
                )

            timeout = aiohttp.ClientTimeout(total=self.valves.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        # error handling emittr
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

                    # If not using streaming, simply return full JSON response
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

                    # STREAMING LOGIC: reads chunked response and emit parsed pieces
                    aggregated_parts: List[str] = []
                    # streaming logic for chunking
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        try:
                            text_chunk = chunk.decode(errors="ignore")
                        except Exception:
                            text_chunk = str(chunk)

                        # split into lines in case multiple json entries arrived in this chunk
                        for raw_line in text_chunk.splitlines():
                            line = raw_line.strip()
                            if not line:
                                continue
                            # SSE sometimes prefixes 'data: ' so we account for that
                            if line.startswith("data:"):
                                line = line[len("data:") :].strip()
                            # ignore stream end markers in case a frontend is stupid
                            if line in ("[DONE]", "DONE"):
                                continue
                            parsed = None
                            try:
                                parsed = json.loads(line)
                            except Exception:
                                # partial JSON or raw text; wrap as raw
                                parsed = {"raw": line}

                            # try to extract readable text from parsed object
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
                                # stream event with the parsed JSON (best effort, i'm not trying harder.)
                                # this is fucked, luckily it doesn't matter
                                await __event_emitter__(
                                    {"type": "stream", "data": parsed}
                                )

                    # complete streaming logic, aggregrate and display an emitter
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
            # error handling
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

