.PHONY: dev-server dev-web dev migrate seed build docker

# Development
dev-server:
	cd server && go run ./cmd/server

dev-web:
	cd web && npm run dev

dev:
	$(MAKE) -j2 dev-server dev-web

# Database
migrate:
	cd server && go run ./cmd/server

seed:
	cd server && go run ./cmd/seed --data-dir=../seed-data

# Build
build-web:
	cd web && npm ci && npm run build

build-server: build-web
	cp -r web/out/* server/static/
	cd server && CGO_ENABLED=0 go build -o ../rpg-scribe ./cmd/server

build: build-server

# Docker
docker:
	docker build -f deploy/Dockerfile -t rpg-scribe:latest .
