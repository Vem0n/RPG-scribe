package seed

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/jackc/pgx/v5/pgxpool"
)

type SeedGame struct {
	Slug string `json:"slug"`
	Name string `json:"name"`
}

type SeedStage struct {
	StageKey  string `json:"stage_key"`
	Name      string `json:"name"`
	SortOrder int    `json:"sort_order"`
}

type SeedQuest struct {
	QuestKey     string      `json:"quest_key"`
	Name         string      `json:"name"`
	Description  string      `json:"description"`
	Category     string      `json:"category"`
	Location     string      `json:"location"`
	SortOrder    int         `json:"sort_order"`
	GuideContent string      `json:"guide_content"`
	Stages       []SeedStage `json:"stages"`
}

type SeedFile struct {
	Game   SeedGame    `json:"game"`
	Quests []SeedQuest `json:"quests"`
}

func LoadAndSeed(ctx context.Context, pool *pgxpool.Pool, dataDir string) error {
	files, err := filepath.Glob(filepath.Join(dataDir, "*.json"))
	if err != nil {
		return fmt.Errorf("globbing seed files: %w", err)
	}
	if len(files) == 0 {
		return fmt.Errorf("no seed files found in %s", dataDir)
	}

	for _, file := range files {
		if err := seedFile(ctx, pool, file); err != nil {
			return fmt.Errorf("seeding %s: %w", filepath.Base(file), err)
		}
	}

	return nil
}

func seedFile(ctx context.Context, pool *pgxpool.Pool, path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("reading file: %w", err)
	}

	var sf SeedFile
	if err := json.Unmarshal(data, &sf); err != nil {
		return fmt.Errorf("parsing json: %w", err)
	}

	tx, err := pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	var gameID int
	err = tx.QueryRow(ctx,
		`INSERT INTO games (slug, name) VALUES ($1, $2)
		 ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
		 RETURNING id`,
		sf.Game.Slug, sf.Game.Name,
	).Scan(&gameID)
	if err != nil {
		return fmt.Errorf("upserting game: %w", err)
	}

	for _, q := range sf.Quests {
		var questID int
		var location *string
		if q.Location != "" {
			location = &q.Location
		}
		err = tx.QueryRow(ctx,
			`INSERT INTO quests (game_id, quest_key, name, description, category, location, sort_order, guide_content)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
			 ON CONFLICT (game_id, quest_key) DO UPDATE SET
				name = EXCLUDED.name,
				description = EXCLUDED.description,
				category = EXCLUDED.category,
				location = EXCLUDED.location,
				sort_order = EXCLUDED.sort_order,
				guide_content = EXCLUDED.guide_content
			 RETURNING id`,
			gameID, q.QuestKey, q.Name, q.Description, q.Category, location, q.SortOrder, q.GuideContent,
		).Scan(&questID)
		if err != nil {
			return fmt.Errorf("upserting quest %s: %w", q.QuestKey, err)
		}

		for _, s := range q.Stages {
			_, err = tx.Exec(ctx,
				`INSERT INTO quest_stages (quest_id, stage_key, name, sort_order)
				 VALUES ($1, $2, $3, $4)
				 ON CONFLICT (quest_id, stage_key) DO UPDATE SET
					name = EXCLUDED.name,
					sort_order = EXCLUDED.sort_order`,
				questID, s.StageKey, s.Name, s.SortOrder,
			)
			if err != nil {
				return fmt.Errorf("upserting stage %s: %w", s.StageKey, err)
			}
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("commit: %w", err)
	}

	fmt.Printf("seeded %s: %d quests\n", sf.Game.Name, len(sf.Quests))
	return nil
}
