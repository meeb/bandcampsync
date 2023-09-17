docker=/usr/bin/docker
name=bandcampsync
image=$(name):latest


container:
	$(docker) build -t $(image) .


runcontainer:
	$(docker) run --rm --name $(name) --env-file dev.env -ti $(image)
