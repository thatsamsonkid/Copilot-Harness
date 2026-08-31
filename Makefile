.PHONY: setup test clone templates bootstrap workspaces create-workspace doctor init status handoff

setup:
	./scripts/setup.sh

test:
	uv run pytest

clone:
	./scripts/clone-repos.sh

templates:
	uv run goat templates

bootstrap:
	@test -n "$(TEMPLATE)" && test -n "$(NAME)" || (echo "Usage: make bootstrap TEMPLATE=spartan-stack NAME=my-app" >&2; exit 2)
	uv run goat bootstrap --template $(TEMPLATE) --name $(NAME)

workspaces:
	uv run goat workspace generate

create-workspace:
	uv run goat workspace create

doctor:
	uv run goat doctor

init:
	uv run goat init

status:
	uv run goat status

handoff:
	uv run goat handoff latest
