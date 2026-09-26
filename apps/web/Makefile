.PHONY: setup dev build test lint clean

SECRETS := ~/.secrets/kanban-treemap.env

setup:
	pnpm install

dev:
	dotenvx run -f $(SECRETS) -- sh -c 'pnpm vite --port $${PORT_WEB} --strictPort'

build:
	pnpm build

test: ;

lint:
	pnpm typecheck

clean:
	rm -rf node_modules
