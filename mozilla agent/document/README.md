# Know Your Docs — Starter Kit

**Build an agent that knows your private stuff and can search the web for the rest.**

This starter kit gives you a working local RAG pipeline and the scaffolding to turn it into a multi-tool agent. Your job is to add web search, build the routing logic, and make something useful.

## What's In The Box

```
know-your-docs-starter-kit/
├── README.md                ← You are here
├── .mcpd.toml               ← MCP server config (mcpd)
├── pyproject.toml            ← Python dependencies
├── corpus/
│   └── sample/              ← Sample docs to verify setup
│       ├── architecture.md
│       ├── runbook.md
│       └── api-spec.md
├── scripts/
│   ├── ingest.py            ← Chunk + embed docs into local vector store
│   ├── rag_mcp_server.py    ← RAG pipeline exposed as an MCP tool
│   └── verify.py            ← Smoke test: question → answer
├── agent/
│   └── main.py              ← YOUR AGENT — start here
├── tools/
│   └── ddgs-mcp-server/     ← Local wrapper for free DDGS web search
└── eval/
    ├── questions.yaml        ← Test questions template
    └── run_eval.py           ← Score your agent
```

## Prerequisites

Install these before the hackathon starts:

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)** (Python package manager)
- **[mcpd](https://github.com/mozilla-ai/mcpd)** — `brew tap mozilla-ai/tap && brew install mcpd`
- **[encoderfile](https://github.com/mozilla-ai/encoderfile)** — download a model binary (see below)
- **[llamafile](https://github.com/Mozilla-Ocho/llamafile)** — download a model binary (see below)

### Download Models

**Encoderfile (embeddings):**

```bash
# URL for all builds:      https://huggingface.co/mozilla-ai/encoderfile/tree/main/sentence-transformers/all-MiniLM-L6-v2
# all-MiniLM-L6-v2 encoder (~80MB) — pick the file for your architecture:
# macOS (Apple Silicon):  all-MiniLM-L6-v2-aarch64-apple-darwin.encoderfile
# macOS (Intel):          all-MiniLM-L6-v2-x86_64-apple-darwin.encoderfile
# Linux (x86_64):         all-MiniLM-L6-v2-x86_64-unknown-linux-gnu.encoderfile
# Windows (x86_64):       all-MiniLM-L6-v2-x86_64-pc-windows-msvc.encoderfile
curl -L -o minilm.encoderfile <PASTE_URL_FOR_YOUR_ARCHITECTURE>
chmod +x minilm.encoderfile
```

**Llamafile (generation):**

```bash
# Download a small model — Mistral 7B or Phi-3 Mini recommended
# See https://github.com/Mozilla-Ocho/llamafile#quickstart
curl -L -o gemma4.llamafile https://huggingface.co/mozilla-ai/llamafile_0.10/resolve/main/gemma-4-E4B-it-Q5_K_M.llamafile
chmod +x gemma4.llamafile
```

## Setup 

### 1. Install Python dependencies

```bash
cd know-your-docs-starter-kit
uv sync
```

### 2. Start your models

Open two terminals:

```bash
# Terminal 1: Encoderfile (embeddings) — REST API mode
./minilm.encoderfile serve --http-port 8085 --disable-grpc

# Terminal 2: Llamafile (generation)
./gemma4.llamafile --port 8086
```

### 3. Ingest the sample corpus

```bash
uv run python scripts/ingest.py --corpus-dir corpus/sample --encoderfile-url http://localhost:8085
```

This chunks the documents and embeds them into a local vector store at `./vector_store.json`.

### 4. Verify it works

```bash
uv run python scripts/verify.py "What is the retry policy for failed payments?"
```

You should get an answer grounded in the sample architecture doc.

### 5. Start mcpd

Install the local RAG MCP server once, then start `mcpd` from the project root.

```bash
uv tool install --editable . --force

mcpd daemon --dev --log-level=DEBUG --log-path ./mcpd.log --runtime-file secrets.prod.toml
```

This starts the mcpd daemon and manages your MCP servers. The default
`.mcpd.toml` starts with just:
- **rag** — your local RAG pipeline (the `rag_mcp_server.py` script)

Once `rag` is working, the recommended next step is to add `ddgs` for free web search.

### 6. Test mcpd

```bash
# List available tools
curl -s http://localhost:8090/api/v1/servers | jq

# Test the RAG tool
curl -s --request POST \
  --url http://localhost:8090/api/v1/servers/rag/tools/search_docs \
  --header 'Content-Type: application/json' \
  --data '{"query": "retry policy"}' | jq
```

**Milestone:** You asked a question and got a grounded answer. The stack works. ✅

If `curl /api/v1/servers` is empty or `mcpd` exits right away, check `./mcpd.log`
first. The most common setup issue is that `rag-mcp-server` was never installed.


## Add Web Search

Once local RAG is working, install the local `ddgs` wrapper once, then
uncomment the bundled `ddgs` block in `.mcpd.toml` and restart `mcpd`.

`ddgs` is the recommended hackathon search server because students can use it
without paying for an API key. It gives you:
- `search_text` for general web search
- `search_news` for news and recency-sensitive questions
- `extract_content` for pulling readable content from a URL

```bash
uv tool install --editable ./tools/ddgs-mcp-server --force
```

After you uncomment the `ddgs` block, restart `mcpd` and verify both servers:

```bash
curl -s http://localhost:8090/api/v1/servers | jq

curl -s --request POST \
  --url http://localhost:8090/api/v1/servers/ddgs/tools/search_text \
  --header 'Content-Type: application/json' \
  --data '{"query": "Stripe API rate limit"}' | jq
```

If you want to read a specific page in more detail, call `extract_content`
after `search_text` returns a promising URL.

You can still add other MCP servers later if you want, but `rag` + `ddgs` is a
strong default for the hackathon.

**Milestone:** `curl http://localhost:8090/api/v1/servers | jq` shows `rag` and `ddgs`. ✅

---

## Build Your Agent 

Open `agent/main.py` — this is where your hackathon work lives.

The skeleton uses `tinyagent` with the `mcpd` Python SDK to pull tools from mcpd and build an agent:

```bash
uv run python agent/main.py "How does our retry logic compare to industry best practices?"
```

This is the hybrid query — the agent should check local docs for "our retry logic" and web sources for "industry best practices."

See `agent/main.py` for the full scaffold and comments.

**Milestone:** Your agent answers a question using both local docs and web search tools in one response. ✅

---

## Evaluate (Hour 4)

Edit `eval/questions.yaml` with your test questions, then run:

```bash
uv run python eval/run_eval.py
```

This runs your questions through the agent and scores routing correctness and answer quality.

**Milestone:** You have a score sheet comparing local-only, external-only, and hybrid queries. ✅

---

## Swapping Your Corpus

Replace the sample docs with your own:

1. Drop `.md` or `.txt` files into a new folder under `corpus/`
2. Re-run ingestion: `uv run python scripts/ingest.py --corpus-dir corpus/your-folder --encoderfile-url http://localhost:8085`
3. Update your agent's instructions in `agent/main.py` to match your domain

---

## Tips

- **llamafile is your LLM** — all generation goes through it. If answers are slow, try a smaller model (Phi-3 Mini, TinyLlama).
- **encoderfile is your embedder** — fast and deterministic. Don't overthink the embedding model; `all-MiniLM-L6-v2` is a solid default.
- **mcpd is your tool manager** — every MCP server lives here. Don't hardcode tool endpoints in your agent.
- **tinyagent is your orchestrator** — it is the default agent runtime in this starter kit.

---

## Resources

- [encoderfile docs](https://docs.mozilla.ai/encoderfile/)
- [llamafile quickstart](https://docs.mozilla.ai/llamafile/getting-started/quickstart)
- [mcpd docs](https://mozilla-ai.github.io/mcpd/)
- [mcpd Python SDK](https://github.com/mozilla-ai/mcpd-sdk-python)
- [encoderfile local-rag example](https://github.com/mozilla-ai/encoderfile/tree/main/examples/local-rag)
- [MCP server directory](https://github.com/modelcontextprotocol/servers)
