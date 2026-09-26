.PHONY: setup dev build test lint clean

setup:
	$(MAKE) -C apps/api setup
	$(MAKE) -C apps/web setup

dev:
	@trap 'kill 0' INT; \
	$(MAKE) -C apps/api dev & \
	$(MAKE) -C apps/web dev & \
	wait

build:
	$(MAKE) -C apps/web build
	$(MAKE) -C apps/api build

test:
	$(MAKE) -C apps/api test
	$(MAKE) -C apps/web test

lint:
	$(MAKE) -C apps/api lint
	$(MAKE) -C apps/web lint

clean:
	$(MAKE) -C apps/api clean
	$(MAKE) -C apps/web clean
