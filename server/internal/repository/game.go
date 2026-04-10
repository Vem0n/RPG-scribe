package repository

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rpg-scribe/server/internal/model"
)

type GameRepo struct {
	pool *pgxpool.Pool
}

func NewGameRepo(pool *pgxpool.Pool) *GameRepo {
	return &GameRepo{pool: pool}
}

func (r *GameRepo) List(ctx context.Context) ([]model.Game, error) {
	rows, err := r.pool.Query(ctx, `SELECT id, slug, name, created_at FROM games ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var games []model.Game
	for rows.Next() {
		var g model.Game
		if err := rows.Scan(&g.ID, &g.Slug, &g.Name, &g.CreatedAt); err != nil {
			return nil, err
		}
		games = append(games, g)
	}
	return games, rows.Err()
}

func (r *GameRepo) GetBySlug(ctx context.Context, slug string) (*model.Game, error) {
	var g model.Game
	err := r.pool.QueryRow(ctx,
		`SELECT id, slug, name, created_at FROM games WHERE slug = $1`,
		slug,
	).Scan(&g.ID, &g.Slug, &g.Name, &g.CreatedAt)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	return &g, err
}
