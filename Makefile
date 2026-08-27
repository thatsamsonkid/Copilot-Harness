.PHONY: setup test clone workspaces doctor

setup:
	./scripts/setup.sh

test:
	uv run pytest

clone:
	./scripts/clone-repos.sh

workspaces:
	uv run harness workspace generate

doctor:
	uv run harness doctor
