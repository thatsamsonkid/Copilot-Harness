.PHONY: setup test clone templates bootstrap workspaces create-workspace doctor init status handoff

setup:
	./scripts/setup.sh

test:
	uv run pytest

clone:
	./scripts/clone-repos.sh

templates:
	uv run harness templates

bootstrap:
	@test -n "$(TEMPLATE)" && test -n "$(NAME)" || (echo "Usage: make bootstrap TEMPLATE=spartan-stack NAME=my-app" >&2; exit 2)
	uv run harness bootstrap --template $(TEMPLATE) --name $(NAME)

workspaces:
	uv run harness workspace generate

create-workspace:
	uv run harness workspace create

doctor:
	uv run harness doctor

init:
	uv run harness init

status:
	uv run harness status

handoff:
	uv run harness handoff latest
