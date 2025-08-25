## Deep Search tool for Open-WebUI (Jina.ai based)
This is a fully independent DeepSearch tool written in Python, specifically built for integration with Open-WebUI. It utilises Jina's DeepSearch model to off-load searching to keep local LLM context contamination free and prevent slow-down. This tool can use several hundred thousand up to several million tokens per search depending on settings. If you're concerned about context window, don't be. The fetched context to injected context ratio is around 60:1. (e.g., a DeepSearch using 1.2m tokens will inject roughly ~20K tokens into your LLM.) How? Jina's DeepSearch model is the agent visiting all of the pages *for* your model. It then provides all relevant context in a JSON string, dramatically reducing token injection.

This makes DeepSearching viable even on consumer and edge devices.

### What's the difference between 'DeepSearch' and a normal search?
Simply put, DeepSearch uses standard key-word search with a twist, allowing you to instruct your model to search through hundreds or thousands of URLs based on context and extract the content from each. It functions the same way as OpenAI DeepResearch, Gemini Deep Think Research, etc. **This is not a tool that 'changes' your LLM into a reasoning model, it merely uses a reasoning model to fetch results.** which can then be interepted by *your* model.

### Can I tweak or customize it?
Yes. The tool provides 8 different valves you can edit. All of this can easily be done via Open-WebUI in the tool interface.

Valves:
1. **Jina API Key** (technically optional, see next section for more info.) - Allows adjusting the main API key to be used.
2. **Timeout Request Limit** (in seconds) - Adjusts how long the tool will try to connect to Jina.ai before dropping connection.
3. **Reasoning Effort** - low, med, high. (Adjusts total *potential* token use. Low maxes at 500K, med at 1M, high at 2M.) Please note, **more than the tokens listed here may be used**. This is generally a non issue as we're talking +-50-100K tokens, but for those lacking on tokens, it's worth noting.
4. **Token Budget**: This allows you to set a maximum budget for searching. This overrides reasoning effort.
5. **Max Returned URLs**: Defines the maximum amount of URLs that are included & considered in the final answer.
6. **Direct Answer (optional)**: Some models are too keen to provide summaries. Enabling this forces the model to output a detailed response and prevents short, direct answers from being generated while using DeepSearch.
7. **Team Size**: The amount of agents to employ for DeepSearch. This functions similar to Grok-4-Heavy, wherein multiple Agents/Models (Jina DeepSearch LLM) simutanelously search the web and work together to find the most relevant results. Strongly recommended to use 2+ agents, although 1 is just fine too. This increases token usage linearly depending on reasoning effort, for example: using low reasoning (500K max tokens) +  employing 2 agents will double the token use to ~1M.
8. **Streaming**: This simply enables or disables streaming. This functions identically to how typical LLM response streaming works. This option is purely preference, and is slightly buggy due to how Open-WebUI is programmed.

### Does this require payment? What about API keys?
* **API Keys (Jina.AI)**: This tool *does* require a valid Jina API key. Luckily, Jina offers up to 20M tokens on your first API key for free. You can grab one from their website (Jina.AI) and use it for this tool. Just keep in mind that even 20M tokens isn't that much in the grand scheme of things if you're using this tool often. Which brings us to the next point...
* **Payment?**: As FOSS, of course you do not have to pay to use this tool itself. You technically do not have to pay Jina either, but you'll quickly run into issues if you want to use this tool frequently. It is therefore recommended to "top-up" your API key with as many tokens as you think you might need/want. Jina offer 1 billion tokens for $50, which I'd recommend. It's the only way I was able to build this tool.

### Privacy?
I am not affiliated with Jina, nor Open-WebUI. This tool collects no information on you and merely provides a useful feature. However, as it does rely on an external service (Jina), I cannot absolutely guarantee no data is collected on their part. I recommend checking their terms and conditions + privacy policy for more information if you're concerned or interested.

### Installation/Setup
Now that we've gone over all the important crap, here's how to actually use this project. It doesn't matter how you import it.

1. You can grab the raw source code and add it in OWI by going to Workspace>Tools>Create>Paste code.
2. Visit https://openwebui.com/t/ayylmaonade/deepsearch and directly import the tool by clicking "Get".
3. Convert to .json and import the tool in OWI under Workspace>Tools>Import Tool. (You're insane if you do this.)
4. Add your Jina API key, and optionally customize the valves for optimal results.

## Your rights & LICENSE
**This project is licensed under the GNU GPLv3. Everything here is entirely free and open source. You may copy, modify, use, and distribute these files to your hearts content without informing me. COMMERCIAL USE PROHIBITED. IF THERE IS ENOUGH DEMAND, I MAY RE-LICENSE IT UNDER MIT OR APACHE 2.0 TO ALLOW FOR COMMERCIAL USE.
PLEASE REFER TO LICENSE.md FOR MORE INFORMATION ON YOUR RIGHTS.**
