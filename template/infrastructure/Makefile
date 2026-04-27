# Claude Code autonomy sandbox — Makefile template.
# --------------------------------------------------
# Convenience wrappers over `docker compose run --rm aiw <cmd>`.
# All targets idempotent.
#
#   make build      — build sandbox image
#   make sync       — uv sync inside container (first-time setup;
#                     also rerun after manifest edits)
#   make test       — your project's test gate
#   make lint       — your project's lint / layer / typecheck gate
#   make smoke      — your release smoke (pre-publish gate)
#   make gates      — sync + test + lint + smoke
#   make shell      — interactive bash inside container
#   make down       — stop containers + drop named volumes (nukes
#                     auth + venv; rerun `make sync` + claude /login)
#   make clean      — `down` + remove the sandbox image
#
# Replace the gate commands below with whatever your stack uses.
# Test/lint/smoke are placeholders — Python defaults shown.

DC      := docker compose
SVC     := aiw
RUN     := $(DC) run --rm $(SVC)

.PHONY: build sync test lint smoke gates shell down clean

build:
	$(DC) build

sync:
	$(RUN) uv sync --frozen

test:
	$(RUN) uv run pytest -q

lint:
	$(RUN) bash -c 'uv run lint-imports && uv run ruff check'

smoke:
	$(RUN) bash scripts/release_smoke.sh

gates: sync test lint smoke

shell:
	$(RUN) bash

down:
	$(DC) down --volumes

clean: down
	-docker rmi claude-autonomy-sandbox:latest
