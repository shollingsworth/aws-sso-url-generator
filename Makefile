.DEFAULT_GOAL := help
help:
	@echo "Available commands:"
	@echo
	@cat Makefile | grep '^\w.*:$$' | cut -d ':' -f 1 | grep -v '^help$$'

TAG := v1.0.0
BASE := hollingsworthsteven/aws-sso-url-generator

hello:
	@echo "Hello, world!"

build:
	docker build -t $(BASE):$(TAG) .

deploy: build
	docker push $(BASE):$(TAG)
	docker tag $(BASE):$(TAG) $(BASE):latest
	docker push $(BASE):latest
