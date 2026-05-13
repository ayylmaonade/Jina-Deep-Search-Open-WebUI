"""
title: Jina DeepSearch Filter (Original Prompts + Robust Logic)
author: ayylmaonade
requirements: aiohttp, pydantic
version: 1.4.0
description: DeepSearch with dropdown controls for effort, team size, and detail level.
"""

from pydantic import BaseModel, Field
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
import json
import time

# Module-level constants for dropdown options
REASONING_EFFORTS = ["low", "medium", "high"]
TEAM_SIZES = ["1", "2", "3", "4"]
RESPONSE_DETAIL_LEVELS = ["concise", "detailed", "comprehensive"]


class Filter:
    """
    Jina DeepSearch Filter with local LLM summarization and robust parsing.
    """

    class Valves(BaseModel):
        jina_api_key: str = Field(
            "", description="Your Jina DeepSearch API key (Bearer token)"
        )
        llm_api_url: str = Field(
            "http://localhost:1234/v1/chat/completions",
            description="Your LLM API endpoint (LLM for summarization of current reasoning in emitter if you want to use an external model.)",
        )
        timeout_seconds: int = Field(
            600, description="Timeout for HTTP requests (seconds)"
        )
        reasoning_effort: str = Field(
            "low",
            description="Reasoning effort level for DeepSearch",
            json_schema_extra={"enum": REASONING_EFFORTS},
        )
        budget_tokens: Optional[int] = Field(
            default=None,
            description="Token budget for the request. If set, overrides reasoning effort.",
        )
        max_returned_urls: int = Field(
            50,
            description="Number of returned URLs that will be considered in the request and answer",
        )
        no_direct_answer: bool = Field(
            True, description="Ask model to avoid direct short answers"
        )
        team_size: int = Field(
            4,
            description="Number of AI researchers in the team (1-4)",
            json_schema_extra={"enum": [int(x) for x in TEAM_SIZES]},
        )
        stream: bool = Field(True, description="Stream results from DeepSearch API")
        show_reasoning: bool = Field(
            True, description="Show DeepSearch reasoning with intelligent summaries"
        )
        update_interval_seconds: int = Field(
            3, description="How often to update reasoning progress (seconds)"
        )
        response_detail_level: str = Field(
            "comprehensive",
            description="How detailed the final response should be",
            json_schema_extra={"enum": RESPONSE_DETAIL_LEVELS},
        )

    class UserValves(BaseModel):
        reasoning_effort: str = Field(
            "low",
            description="Your preferred reasoning effort level",
            json_schema_extra={"enum": REASONING_EFFORTS},
        )
        budget_tokens: Optional[int] = Field(
            default=None,
            description="Token budget for the request. If set, overrides reasoning effort.",
        )
        team_size: int = Field(
            4,
            description="Number of AI researchers in the team (1-4)",
            json_schema_extra={"enum": [int(x) for x in TEAM_SIZES]},
        )
        response_detail_level: str = Field(
            "comprehensive",
            description="How detailed you want the final response",
            json_schema_extra={"enum": RESPONSE_DETAIL_LEVELS},
        )
        max_returned_urls: int = Field(
            50,
            description="Number of returned URLs to consider in the answer",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        **kwargs,
    ) -> dict:
        if (
            not hasattr(self, "toggle")
            or not self.toggle
            or not self.valves.jina_api_key
        ):
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        # Get the last user message and its index
        last_user_msg = None
        last_user_idx = -1
        for i, msg in enumerate(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                last_user_idx = i

        if not last_user_msg or not isinstance(last_user_msg, str):
            return body

        # Extract user valves
        user_valves = __user__.get("valves") if __user__ else None

        # Get effective values (user valves override global valves)
        reasoning_effort = (
            user_valves.reasoning_effort
            if user_valves
            else self.valves.reasoning_effort
        )
        budget_tokens = (
            user_valves.budget_tokens if user_valves else self.valves.budget_tokens
        )
        team_size = (
            user_valves.team_size
            if user_valves and hasattr(user_valves, "team_size")
            else self.valves.team_size
        )
        response_detail_level = (
            user_valves.response_detail_level
            if user_valves
            else self.valves.response_detail_level
        )
        max_returned_urls = (
            user_valves.max_returned_urls
            if user_valves
            else self.valves.max_returned_urls
        )

        try:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "🔍 Starting DeepSearch...",
                            "done": False,
                        },
                    }
                )

            search_result = await self._deepsearch_query(
                last_user_msg,
                __event_emitter__,
                reasoning_effort,
                budget_tokens,
                team_size,
                response_detail_level,
                max_returned_urls,
            )

            # RESTORED ORIGINAL PROMPT LOGIC
            # Add system message if it doesn't exist
            if not any(msg.get("role") == "system" for msg in messages):
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": (
                            "You are an expert research assistant. When provided with DeepSearch results, "
                            "you synthesize them into comprehensive, detailed, and well-structured answers. "
                            "Include specific findings, cite sources where relevant from the results, explain implications, "
                            "and provide nuanced analysis. Be thorough and informative.\n\n"
                            "CRITICAL: Do NOT use any search tools, web search functions, or external lookup capabilities. "
                            "All research has already been completed via DeepSearch. Use ONLY the provided research findings to answer the question. "
                            "Do not attempt to search for additional information."
                        ),
                    },
                )

            # Enrich the message with search results and explicit instructions
            messages[last_user_idx]["content"] = (
                f"Based on the context, answer this question in detail:\n\n"
                f"Question: {last_user_msg}\n\n"
                f"=== Research Findings ===\n{search_result}\n\n"
                f"Provide a well-formatted, comprehensive, thorough, detailed answer that:\n"
                f"- Synthesizes the research findings above\n"
                f"- Include all details from the research findings\n"
                f"- Use headers, bullet-pointed lists, and if appropriate, summary tables, to make it scannable and readable\n"
                f"- Includes specific data, statistics, or findings from the research\n"
                f"- Explains the implications and significance\n"
                f"- Addresses multiple perspectives if relevant\n"
                f"- Cites sources where appropriate\n\n"
                f"Answer:"
            )

            body["messages"] = messages

            # CRITICAL: Disable tool calling to prevent redundant searches
            body["tool_choice"] = "none"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "✅ DeepSearch complete", "done": True},
                    }
                )

        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"❌ DeepSearch error: {str(e)[:50]}",
                            "done": True,
                        },
                    }
                )
        return body

    async def _deepsearch_query(
        self,
        query: str,
        __event_emitter__=None,
        reasoning_effort: str = None,
        budget_tokens: Optional[int] = None,
        team_size: int = None,
        response_detail_level: str = None,
        max_returned_urls: int = None,
    ) -> str:
        url = "https://deepsearch.jina.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.valves.jina_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "jina-deepsearch-v1",
            "messages": [{"role": "user", "content": query}],
            "stream": self.valves.stream,
            "reasoning_effort": reasoning_effort,
            "max_returned_urls": str(max_returned_urls),
            "no_direct_answer": self.valves.no_direct_answer,
            "team_size": team_size,
        }
        if budget_tokens:
            payload["budget_tokens"] = budget_tokens

        final_content = ""
        reasoning_buffer = ""
        last_emit_time = time.time()

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.valves.timeout_seconds)
        ) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    return f"API Error {resp.status}: {await resp.text()}"

                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            parsed = json.loads(line[6:])
                            delta = (
                                parsed["choices"][0].get("delta", {}).get("content", "")
                            )
                            final_content += delta
                            reasoning_buffer += delta
                        except:
                            continue

                    # Local summarizing trigger
                    if (
                        self.valves.show_reasoning
                        and (time.time() - last_emit_time)
                        >= self.valves.update_interval_seconds
                    ):
                        if reasoning_buffer.strip():
                            summary = await self._local_summarize(reasoning_buffer)
                            if __event_emitter__ and summary:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {"description": summary, "done": False},
                                    }
                                )
                            reasoning_buffer = ""  # Flush buffer
                        last_emit_time = time.time()

                return final_content if final_content else "No results found."

    async def _local_summarize(self, text: str) -> Optional[str]:
        """Strict summary logic to maintain UI length and low token cost."""
        if len(text) < 15:
            return None

        # Specific instructions for exactly one status line
        prompt = f"Describe current research task in 6 words starting with -ing. No periods.\nInput: {text[:400]}\nStatus:"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.valves.llm_api_url,
                    json={
                        "model": "local-model",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 12,  # Absolute token ceiling
                        "temperature": 0.2,
                        "stop": ["\n", "."],  # Kill sentence early
                    },
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        res = body["choices"][0]["message"]["content"].strip()
                        # Strict UI truncation at 50 chars for the UI layout
                        return f"🌐 {res[:50]}..." if len(res) > 50 else f"🌐 {res}"
        except:
            pass
        return "🌐 Performing DeepSearch..."
