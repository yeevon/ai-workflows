# ai-workflows sandbox Makefile
# -----------------------------
# Convenience wrappers around `docker compose run --rm aiw <cmd>`.
# All targets are idempotent.
#
#   make build      — build the sandbox image
#   make sync       — uv sync inside the container (first-time setup;
#                     also rerun after pyproject.toml / uv.lock edits)
#   make test       — uv run pytest -q
#   make lint       — uv run lint-imports + uv run ruff check
#   make smoke      — bash scripts/release_smoke.sh (all 7 stages)
#   make gates      — sync + test + lint + smoke (the full release
#                     ceremony minus uv publish)
#   make shell      — interactive bash inside the container
#   make down       — stop containers + drop named volumes (nuke
#                     the venv cache; rerun `make sync` after)
#   make clean      — `down` + remove the sandbox image
#
# Layer over the Makefile, not under it: a future autonomous-mode
# skill will call these targets directly.

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
	-docker rmi ai-workflows-sandbox:latest
