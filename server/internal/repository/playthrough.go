package repository

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rpg-scribe/server/internal/model"
)

type PlaythroughRepo struct {
	pool *pgxpool.Pool
}

func NewPlaythroughRepo(pool *pgxpool.Pool) *PlaythroughRepo {
	return &PlaythroughRepo{pool: pool}
}

func (r *PlaythroughRepo) FindOrCreate(ctx context.Context, userID, gameID int, externalID, name string) (*model.Playthrough, error) {
	var p model.Playthrough
	err := r.pool.QueryRow(ctx,
		`INSERT INTO playthroughs (user_id, game_id, external_id, name)
		 VALUES ($1, $2, $3, $4)
		 ON CONFLICT (user_id, game_id, external_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
		 RETURNING id, user_id, game_id, name, external_id, last_synced_at, created_at, updated_at`,
		userID, gameID, externalID, name,
	).Scan(&p.ID, &p.UserID, &p.GameID, &p.Name, &p.ExternalID, &p.LastSyncedAt, &p.CreatedAt, &p.UpdatedAt)
	return &p, err
}

func (r *PlaythroughRepo) UpdateLastSynced(ctx context.Context, playthroughID int) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE playthroughs SET last_synced_at = now(), updated_at = now() WHERE id = $1`,
		playthroughID,
	)
	return err
}

func (r *PlaythroughRepo) ListByUser(ctx context.Context, username string) ([]model.PlaythroughWithGame, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT
			p.id, p.user_id, p.game_id, p.name, p.external_id, p.last_synced_at, p.created_at, p.updated_at,
			g.id, g.slug, g.name, g.created_at,
			COALESCE(qs.total, 0),
			COALESCE(qs.finished, 0),
			COALESCE(qs.started, 0),
			COALESCE(qs.failed, 0),
			COALESCE(qs.unstarted, 0)
		FROM playthroughs p
		JOIN users u ON u.id = p.user_id
		JOIN games g ON g.id = p.game_id
		LEFT JOIN LATERAL (
			SELECT
				COUNT(*) AS total,
				COUNT(*) FILTER (WHERE pq.status = 'finished') AS finished,
				COUNT(*) FILTER (WHERE pq.status = 'started') AS started,
				COUNT(*) FILTER (WHERE pq.status = 'failed') AS failed,
				COUNT(*) FILTER (WHERE pq.status = 'unstarted') AS unstarted
			FROM playthrough_quests pq
			WHERE pq.playthrough_id = p.id
		) qs ON true
		WHERE u.username = $1
		ORDER BY p.updated_at DESC`,
		username,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var result []model.PlaythroughWithGame
	for rows.Next() {
		var pw model.PlaythroughWithGame
		if err := rows.Scan(
			&pw.ID, &pw.UserID, &pw.GameID, &pw.Name, &pw.ExternalID, &pw.LastSyncedAt, &pw.CreatedAt, &pw.UpdatedAt,
			&pw.Game.ID, &pw.Game.Slug, &pw.Game.Name, &pw.Game.CreatedAt,
			&pw.QuestSummary.Total, &pw.QuestSummary.Finished, &pw.QuestSummary.Started,
			&pw.QuestSummary.Failed, &pw.QuestSummary.Unstarted,
		); err != nil {
			return nil, err
		}
		result = append(result, pw)
	}
	return result, rows.Err()
}

func (r *PlaythroughRepo) GetByID(ctx context.Context, id int) (*model.Playthrough, error) {
	var p model.Playthrough
	err := r.pool.QueryRow(ctx,
		`SELECT id, user_id, game_id, name, external_id, last_synced_at, created_at, updated_at
		 FROM playthroughs WHERE id = $1`,
		id,
	).Scan(&p.ID, &p.UserID, &p.GameID, &p.Name, &p.ExternalID, &p.LastSyncedAt, &p.CreatedAt, &p.UpdatedAt)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	return &p, err
}

func (r *PlaythroughRepo) GetByIDWithGame(ctx context.Context, id int) (*model.PlaythroughWithGame, error) {
	var pw model.PlaythroughWithGame
	err := r.pool.QueryRow(ctx, `
		SELECT
			p.id, p.user_id, p.game_id, p.name, p.external_id, p.last_synced_at, p.created_at, p.updated_at,
			g.id, g.slug, g.name, g.created_at
		FROM playthroughs p
		JOIN games g ON g.id = p.game_id
		WHERE p.id = $1`,
		id,
	).Scan(
		&pw.ID, &pw.UserID, &pw.GameID, &pw.Name, &pw.ExternalID, &pw.LastSyncedAt, &pw.CreatedAt, &pw.UpdatedAt,
		&pw.Game.ID, &pw.Game.Slug, &pw.Game.Name, &pw.Game.CreatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	return &pw, err
}
