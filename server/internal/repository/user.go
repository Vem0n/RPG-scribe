package repository

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rpg-scribe/server/internal/model"
)

type UserRepo struct {
	pool *pgxpool.Pool
}

func NewUserRepo(pool *pgxpool.Pool) *UserRepo {
	return &UserRepo{pool: pool}
}

func (r *UserRepo) List(ctx context.Context) ([]model.User, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT u.id, u.username, u.created_at, u.updated_at,
		       g.slug, g.name
		FROM users u
		LEFT JOIN LATERAL (
			SELECT p.game_id FROM playthroughs p
			WHERE p.user_id = u.id
			ORDER BY p.last_synced_at DESC NULLS LAST
			LIMIT 1
		) lp ON true
		LEFT JOIN games g ON g.id = lp.game_id
		ORDER BY u.username`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []model.User
	for rows.Next() {
		var u model.User
		if err := rows.Scan(&u.ID, &u.Username, &u.CreatedAt, &u.UpdatedAt,
			&u.LastGameSlug, &u.LastGameName); err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, rows.Err()
}

func (r *UserRepo) GetByUsername(ctx context.Context, username string) (*model.User, error) {
	var u model.User
	err := r.pool.QueryRow(ctx,
		`SELECT id, username, password, created_at, updated_at FROM users WHERE username = $1`,
		username,
	).Scan(&u.ID, &u.Username, &u.Password, &u.CreatedAt, &u.UpdatedAt)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	return &u, err
}

func (r *UserRepo) FindOrCreate(ctx context.Context, username string) (*model.User, error) {
	var u model.User
	err := r.pool.QueryRow(ctx,
		`INSERT INTO users (username) VALUES ($1)
		 ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
		 RETURNING id, username, created_at, updated_at`,
		username,
	).Scan(&u.ID, &u.Username, &u.CreatedAt, &u.UpdatedAt)
	return &u, err
}

func (r *UserRepo) SetPassword(ctx context.Context, userID int, hashedPassword string) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE users SET password = $1, updated_at = now() WHERE id = $2`,
		hashedPassword, userID,
	)
	return err
}
