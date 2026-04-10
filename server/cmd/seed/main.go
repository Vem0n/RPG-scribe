package main

import (
	"context"
	"flag"
	"log"

	"github.com/rpg-scribe/server/internal/config"
	"github.com/rpg-scribe/server/internal/database"
	"github.com/rpg-scribe/server/internal/seed"
)

func main() {
	dataDir := flag.String("data-dir", "", "path to seed data directory (overrides SEED_DATA_DIR env)")
	flag.Parse()

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("loading config: %v", err)
	}

	if *dataDir != "" {
		cfg.SeedDataDir = *dataDir
	}

	ctx := context.Background()
	pool, err := database.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("connecting to database: %v", err)
	}
	defer pool.Close()

	log.Printf("seeding from %s...", cfg.SeedDataDir)
	if err := seed.LoadAndSeed(ctx, pool, cfg.SeedDataDir); err != nil {
		log.Fatalf("seeding failed: %v", err)
	}
	log.Println("seeding complete")
}
