FROM node:22-alpine AS web-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM golang:1.23-alpine AS server-builder
WORKDIR /app
COPY server/go.mod server/go.sum ./server/
RUN cd server && go mod download
COPY server/ ./server/
COPY --from=web-builder /app/web/dist/ ./server/static/
RUN cd server && CGO_ENABLED=0 GOOS=linux go build -o /rpg-scribe ./cmd/server
RUN cd server && CGO_ENABLED=0 GOOS=linux go build -o /rpg-scribe-seed ./cmd/seed

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata
COPY --from=server-builder /rpg-scribe /usr/local/bin/rpg-scribe
COPY --from=server-builder /rpg-scribe-seed /usr/local/bin/rpg-scribe-seed
COPY seed-data/ /data/seed-data/
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["entrypoint.sh"]
