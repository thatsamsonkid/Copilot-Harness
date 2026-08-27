.PHONY: setup test clone workspaces create-workspace doctor

setup:
	./scripts/setup.sh

test:
	uv run pytest

clone:
	./scripts/clone-repos.sh

workspaces:
	uv run harness workspace generate

create-workspace:
	uv run harness workspace create

doctor:
	uv run harness doctor
