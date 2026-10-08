# quoteline developer commands. No target reads .env: live targets take GEMINI_API_KEY
# (and OPENALEX_API_KEY for the dataset) from the shell — run `set -a; . ./.env; set +a` first.

API_PORT ?= 8010

.PHONY: setup test lint format eval feed api web dev build-static smoke dataset record

setup:
	uv sync
	npm ci --prefix web

test:
	RUN_MODE=replay uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	npm run lint --prefix web

format:
	uv run ruff format .
	uv run ruff check --fix .

eval:
	RUN_MODE=replay uv run python evals/run_evals.py

feed:
	uv run quoteline feed

api:
	RUN_MODE=live uv run uvicorn quoteline.api:create_app --factory --host 127.0.0.1 --port $(API_PORT)

web:
	API_PORT=$(API_PORT) npm --prefix web run dev

dev:
	@trap 'kill 0' INT TERM; $(MAKE) api & $(MAKE) web & wait

build-static:
	RUN_MODE=replay uv run quoteline export
	VITE_STATIC=1 npm --prefix web run build

smoke:
	RUN_MODE=live uv run quoteline smoke

dataset:  # live: questions (LLM), training arms (network, OpenAlex key), golden judgments (LLM), bandit report
	RUN_MODE=live uv run quoteline dataset-questions
	uv run quoteline dataset-arms
	RUN_MODE=live uv run quoteline dataset-judge
	uv run quoteline bandit

record:  # live LLM calls recorded into cassettes/ and replays/ for the public demo and CI
	RUN_MODE=record uv run quoteline record-demos
	RUN_MODE=replay uv run python evals/run_evals.py
