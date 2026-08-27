.PHONY: setup test clone templates bootstrap workspaces doctor

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

doctor:
	uv run harness doctor
