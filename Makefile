.PHONY: install ingest run dev clean

PYTHON ?= python3

install:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

ingest:
	. .venv/bin/activate && python -m bot.ingest

run:
	. .venv/bin/activate && python -m bot

dev: ingest run

clean:
	rm -rf data/index.pkl __pycache__ bot/__pycache__
