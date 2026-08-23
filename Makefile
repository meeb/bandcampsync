docker=/usr/bin/docker
name=bandcampsync
image=$(name):latest
SRC              ?= $(CURDIR)
MACMINI_SSH_HOST ?= mini.tail85aacc.ts.net
SONARQUBE_PORT   ?= 9001
# Resolve hostname->IP at make-eval time so the scanner container never needs DNS
_MACMINI_IP      := $(shell getent hosts $(MACMINI_SSH_HOST) 2>/dev/null | awk '{print $$1; exit}')
SONARQUBE_URL    ?= http://$(or $(_MACMINI_IP),$(MACMINI_SSH_HOST)):$(SONARQUBE_PORT)
SONAR_CACHE      ?= $(HOME)/.sonar/cache

.PHONY: container runcontainer run test lint format typecheck build scan


container:
	$(docker) build -t $(image) .


runcontainer:
	$(docker) run --rm --name $(name) --env-file dev.env -ti -v ./docker-config:/config -v ./docker-downloads:/downloads $(image)


run:
	mkdir -p ./docker-downloads
	poetry run python ./bin/bandcampsync -c cookies.txt -d docker-downloads


test:
	poetry run pytest -v


lint:
	poetry run ruff check


format:
	poetry run ruff format


typecheck:
	poetry run mypy


build:
	poetry build

## scan: run sonar-scanner against the SonarQube instance on the Mini
## Requires SONARQUBE_API_KEY env var — generate at $(SONARQUBE_URL)/account/security
scan:
	@docker run --rm \
		--network host \
		-v "$(SRC):/usr/src" \
		-v "$(SONAR_CACHE):/root/.sonar/cache" \
		sonarsource/sonar-scanner-cli \
		-Dsonar.projectKey=bandcampsync \
		-Dsonar.sources=. \
		-Dsonar.host.url=$(SONARQUBE_URL) \
		-Dsonar.token=$(SONARQUBE_API_KEY)
