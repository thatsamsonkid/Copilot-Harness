.PHONY: setup test clone templates bootstrap workspaces create-workspace doctor init status handoff

setup:
	./scripts/setup.sh

test:
	uv run pytest

clone:
	./scripts/clone-repos.sh

templates:
	uv run coboose templates

bootstrap:
	@test -n "$(TEMPLATE)" && test -n "$(NAME)" || (echo "Usage: make bootstrap TEMPLATE=spartan-stack NAME=my-app" >&2; exit 2)
	uv run coboose bootstrap --template $(TEMPLATE) --name $(NAME)

workspaces:
	uv run coboose workspace generate

create-workspace:
	uv run coboose workspace create

doctor:
	uv run coboose doctor

init:
	uv run coboose init

status:
	uv run coboose status

handoff:
	uv run coboose handoff latest
