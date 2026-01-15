docker=/usr/bin/docker
name=bandcampsync
image=$(name):latest


container:
	$(docker) build -t $(image) .


runcontainer:
	$(docker) run --rm --name $(name) --env-file dev.env -ti -v ./docker-config:/config -v ./docker-downloads:/downloads $(image)


run:
	mkdir -p ./docker-downloads
	cp ./bin/bandcampsync ./bcs
	uv run ./bcs -c cookies.txt -d docker-downloads
	rm ./bcs


test:
	uv run python -m pytest -v


lint:
	uvx ruff check


format:
	uvx ruff format


build:
	uv build


publish:
	uv publish
