docker=/usr/bin/docker
name=bandcampsync
image=$(name):latest


container:
	$(docker) build -t $(image) .


runcontainer:
	$(docker) run --rm --name $(name) --env-file dev.env -ti -v ./docker-config:/config -v ./docker-downloads:/downloads $(image)


lint:
	uvx ruff check


format:
	uvx ruff format


build:
	uv build


publish:
	uv publish
