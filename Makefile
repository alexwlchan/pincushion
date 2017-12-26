requirements.txt: requirements.in
	docker run --rm --tty --volume $(CURDIR):/src micktwomey/pip-tools

.docker/build: requirements.txt Dockerfile
	docker build --tag pinboard.es .
	mkdir -p .docker
	touch .docker/build

build: .docker/build
