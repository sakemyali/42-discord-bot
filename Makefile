.PHONY: install ingest ingest-replay run webui convert clean ingest-tail ingest-status

PYTHON ?= python3

install:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Build the LightRAG knowledge graph from corpus/.
# Uses whichever LLM provider is configured in .env (auto-detection order:
# GEMINI_API_KEY > GROQ_API_KEY > Ollama). Recommended for fresh builds:
# Groq Dev tier — ~30 min for the full corpus, lifts the free-tier 6K TPM
# cap that blocks LightRAG's entity-extraction prompts.
# Re-runnable: LightRAG dedupes by content hash and resumes failed docs.
ingest:
	. .venv/bin/activate && python -m bot.ingest

# Replay the checked-in cache/claude_responses.json into a fresh LightRAG
# storage. ~14 seconds. Reproduces the exact graph (593 nodes / 269 edges)
# that ships in this repo without spending API tokens. See README → Ingest.
ingest-replay:
	. .venv/bin/activate && python scripts/dump_chunks.py
	. .venv/bin/activate && python scripts/claude_ingest.py

# Start the Discord bot.
run:
	. .venv/bin/activate && python -m bot

# Launch the LightRAG web UI for inspecting the knowledge graph + docs.
# Default port: 9621. Open http://localhost:9621 in a browser.
#
# Embedding dim must match the storage. The bot uses sentence-transformers
# paraphrase-multilingual-MiniLM-L12-v2 (384-d). lightrag-server doesn't
# support sentence-transformers as a binding, so we point it at Ollama's
# all-minilm (also 384-d) — same dim, different model. Effect: the dim
# check passes and the webui starts; graph viz + doc list work fine.
# The webui's "Query" tab will produce off-axis results since the embedder
# differs — use the Discord bot for real answers, the webui for inspection.
webui:
	@command -v ollama >/dev/null && ollama list 2>/dev/null | grep -q "all-minilm" \
		|| (echo "==> pulling all-minilm (384-d, ~46MB)..." && ollama pull all-minilm)
	. .venv/bin/activate && \
		EMBEDDING_BINDING=ollama \
		EMBEDDING_MODEL=all-minilm \
		EMBEDDING_DIM=384 \
		LLM_BINDING=ollama \
		LLM_MODEL=qwen2.5:7b \
		lightrag-server \
			--working-dir $(or $(LIGHTRAG_WORKING_DIR),./rag_storage) \
			--llm-binding ollama \
			--embedding-binding ollama \
			--port 9621

# Convert raw HTML/PDF in Q&A/ to markdown in corpus/intra/.
convert:
	. .venv/bin/activate && python scripts/convert_qa.py

clean:
	rm -rf rag_storage __pycache__ bot/__pycache__ scripts/__pycache__

# Tail the running ingest log.
ingest-tail:
	tail -f /tmp/ingest_run.log

# Show current ingest progress with rate + ETA + last log lines.
ingest-status:
	@.venv/bin/python scripts/ingest_status.py
