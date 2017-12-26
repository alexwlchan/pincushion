requirements.txt: requirements.in
	docker run --rm --tty --volume $(CURDIR):/src micktwomey/pip-tools
