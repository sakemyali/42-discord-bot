.PHONY: install ingest run webui convert clean

PYTHON ?= python3

install:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Run once on a fresh corpus. Slow (LLM extracts entities per chunk).
# Re-runnable: LightRAG resumes from where it left off.
ingest:
	. .venv/bin/activate && python -m bot.ingest

# Start the Discord bot.
run:
	. .venv/bin/activate && python -m bot

# Launch the LightRAG web UI for inspecting the knowledge graph + queries.
# Default port: 9621. Open http://localhost:9621 in a browser.
# Note: webui queries use Ollama bindings; the Discord bot uses sentence-
# transformers, so search results from the webui won't match the bot. Use the
# webui for graph + chunk inspection, the bot for actual answers.
webui:
	. .venv/bin/activate && lightrag-server \
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
