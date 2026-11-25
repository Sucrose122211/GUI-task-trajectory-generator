IMAGE := gui-trajectory:0.1
RUN := docker run --rm --user $$(id -u):$$(id -g) -v "$$(pwd):/work" -w /work --entrypoint sh $(IMAGE)

.PHONY: build check
build:
	docker build -t $(IMAGE) .

check:
	$(RUN) -c 'ruff check src tests && ruff format --check src tests && PYTHONPATH=src python -m unittest discover -s tests -v && pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/wheels .'
	docker run --rm --user $$(id -u):$$(id -g) -v "$$(pwd):/work:ro" -w /work node:22-alpine node --test tests/test_apps_script.cjs
