requirements.txt: requirements.in
	pip-compile requirements.in

test_requirements.txt: test_requirements.in
	pip-compile test_requirements.in

.docker/build: requirements.txt Dockerfile
	docker build --tag pincushion .
	mkdir -p .docker
	touch .docker/build

build: .docker/build

lint:
	docker run --rm --tty \
		--volume $(CURDIR):/src \
		--workdir /src \
		wellcome/flake8:latest --ignore=E501


define terraform
	docker run --rm --tty \
		--volume ~/.aws:/root/.aws \
		--volume $(CURDIR)/terraform:/data \
		--workdir /data \
		hashicorp/terraform $(1)
endef

terraform-plan:
	$(call terraform,init)
	$(call terraform,get)
	$(call terraform,plan) -out terraform.plan

terraform-apply:
	$(call terraform,apply) terraform.plan
