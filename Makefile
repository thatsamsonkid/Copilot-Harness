.PHONY: setup test clone workspaces doctor

setup:
	./scripts/setup.sh

test:
	PYTHONPATH=src python3 -m pytest

clone:
	./scripts/clone-repos.sh

workspaces:
	PYTHONPATH=src python3 -m harness workspace generate

doctor:
	PYTHONPATH=src python3 -m harness doctor
