## Deep Search filter for Open-WebUI (v1.4.0 — Jina.ai based)

This is a fully independent DeepSearch **filter** written in Python, specifically built for integration with Open-WebUI. It uses Jina's DeepSearch model to off-load searching to keep local LLM context contamination free and prevent slow-down. This can use several hundred thousand up to several million tokens per search depending on settings. If you're concerned about context window, don't be. The fetched context to injected context ratio is around 60:1. (e.g., a DeepSearch using 1.2m tokens will inject roughly ~20K tokens into your LLM.) How? Jina's DeepSearch model is the agent visiting all of the pages *for* your model. It then provides all relevant context in a JSON string, dramatically reducing token injection.

This makes DeepSearching viable even on consumer and edge devices.

### What's the difference between 'DeepSearch' and a normal search?

Simply put, DeepSearch uses standard keyword search with a twist, allowing you to instruct your model to search through hundreds or thousands of URLs based on context and extract the content from each. It functions the same way as OpenAI DeepResearch, Gemini Deep Think Research, etc. **This is not a tool that 'changes' your LLM into a reasoning model, it merely uses a reasoning model to fetch results** which can then be interpreted by *your* model.

### How it works (v1.4.0)

Unlike previous versions that worked as a tool the LLM calls, Deep Search v1.4.0 works as a **filter** that intercepts your message before it reaches the LLM. Here's the flow:

1. You type a question in the chat
2. Deep Search intercepts it, queries Jina's DeepSearch API with your settings
3. Results are injected into the message as a `=== Research Findings ===` block
4. A system prompt tells your LLM to use ONLY those findings (no redundant tool calls)
5. The enriched message is passed to your LLM for a comprehensive answer

Real-time progress summaries are streamed back using a local LLM endpoint (optional) — e.g. "🌐 Analyzing academic papers..." — so you can watch the research unfold.

### After installation

After install, "Deep Search" will show up in the "+" menu where other functions like web search, image generation, code interpreter, etc. appear. You can tweak some valves from here — reasoning effort, team size, and response detail. All other valves are admin-only.

### Valves (14 total)

**Admin valves** (set via Open-WebUI Workspace > Tools > Filters):

1. **Jina API Key** — Your Jina DeepSearch API key (Bearer token). Required.
2. **LLM API URL** — Your local LLM endpoint for real-time progress summarization. Default: `http://localhost:1234/v1/chat/completions`. Leave blank to disable progress summaries.
3. **Timeout** (seconds) — Max timeout for Jina requests. **600+ strongly recommended** — this includes time for the DeepSearch to run.
4. **Reasoning Effort** — `low` / `medium` / `high`. Adjusts total potential token use (low ~500K, med ~1M, high ~2M). Note: actual usage may vary ±50-100K.
5. **Token Budget** — Maximum budget for searching. Overrides reasoning effort if set.
6. **Max Returned URLs** — Maximum URLs included in the final answer. Default: 50.
7. **No Direct Answer** — Forces the model to output detailed responses, preventing short summaries.
8. **Team Size** — Number of AI researchers (1-4). Multiple agents search simultaneously. Strongly recommended: 2+. Token usage scales linearly.
9. **Stream Results** — Enable/disable streaming from Jina API.
10. **Show Reasoning** — Enable real-time progress summaries via local LLM.
11. **Update Interval** (seconds) — How often progress summaries are emitted. Default: 3.
12. **Response Detail Level** — `concise` / `detailed` / `comprehensive`. How detailed the final Jina DeepSearch output should be.

**User valves** (adjustable from the chat "+" menu):

13. **Reasoning Effort** — Per-user override for reasoning effort.
14. **Team Size** — Per-user override for team size.
15. **Response Detail Level** — Per-user override for response detail.
16. **Token Budget** — Per-user override for token budget.
17. **Max Returned URLs** — Per-user override for URL count.

### Does this require payment? What about API keys?

- **API Keys (Jina.AI)**: This filter *does* require a valid Jina API key. Jina offers up to 20M tokens on your first API key for free. Grab one from [Jina.AI](https://jina.ai) and use it here. Even 20M tokens won't last long if you use this frequently, which brings us to...
- **Payment?**: As FOSS, of course you don't have to pay for this filter itself. But you'll quickly run into Jina rate limits if you use this often. Topping up your API key is recommended. Jina offers 1 billion tokens for $50.

### Privacy

I am not affiliated with Jina, nor Open-WebUI. This filter collects no information on you and merely provides a useful feature. However, as it relies on an external service (Jina), I cannot absolutely guarantee no data is collected on their part. Check their [terms](https://jina.ai/terms) and [privacy policy](https://jina.ai/privacy) if concerned.

### Installation/Setup

1. Grab the raw source code and paste it in OWI via Workspace > Tools > Create.
2. Visit https://openwebui.com/t/ayylmaonade/deepsearch and import via "Get".
3. Import the `.json` export from OWI under Workspace > Tools > Import Tool.
4. Add your Jina API key in the admin valves.
5. Optional: Toggle 'stream' to **false** in admin valves if you don't need real-time progress. Streaming currently doesn't work perfectly in OWI and wastes tokens, but enables if you want to watch the research unfold.

## Your rights & LICENSE

**This project is licensed under the GNU GPLv3. Everything here is entirely free and open source. You may copy, modify, use, and distribute these files to your hearts content without informing me.**

**IF THERE IS ENOUGH DEMAND, I MAY RE-LICENSE IT UNDER MIT OR APACHE 2.0 TO ALLOW FOR MORE PERMISSIVE COMMERCIAL USE. PLEASE REFER TO 'LICENSE' FOR MORE INFORMATION ON YOUR RIGHTS.**
