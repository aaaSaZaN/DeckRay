# Makefile for DeckRay plugin
# Used by decky-plugin-database CI/CD for packaging

.PHONY: all clean

all:
	pnpm install
	pnpm run build

clean:
	rm -rf dist
