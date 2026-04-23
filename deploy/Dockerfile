# --platform=$BUILDPLATFORM pins the build stages to the host architecture
# (x86_64 on the GitHub runner) instead of letting buildx run them under
# QEMU emulation for each --platform target. Without this, Node 22's V8
# trips QEMU's incomplete instruction emulation and dies with SIGILL during
# `npm ci` when buildx is producing the linux/arm64 layer. Web output is
# pure JS (arch-agnostic) and Go cross-compiles natively via GOOS/GOARCH,
# so neither stage actually needs to run on the target arch.
FROM --platform=$BUILDPLATFORM node:22-alpine AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM --platform=$BUILDPLATFORM golang:1.26-alpine AS server-builder
ARG TARGETOS
ARG TARGETARCH
WORKDIR /app
COPY server/go.mod server/go.sum ./server/
RUN cd server && go mod download
COPY server/ ./server/
COPY --from=web-builder /app/web/dist/ ./server/static/
RUN cd server && CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /rpg-scribe ./cmd/server
RUN cd server && CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /rpg-scribe-seed ./cmd/seed

FROM alpine:3.23
RUN apk add --no-cache ca-certificates tzdata
COPY --from=server-builder /rpg-scribe /usr/local/bin/rpg-scribe
COPY --from=server-builder /rpg-scribe-seed /usr/local/bin/rpg-scribe-seed
COPY seed-data/ /data/seed-data/
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["entrypoint.sh"]
