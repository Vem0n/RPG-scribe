package repository

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/rpg-scribe/server/internal/model"
)

type QuestRepo struct {
	pool *pgxpool.Pool
}

func NewQuestRepo(pool *pgxpool.Pool) *QuestRepo {
	return &QuestRepo{pool: pool}
}

func (r *QuestRepo) GetQuestIDByKey(ctx context.Context, gameID int, questKey string) (int, error) {
	var id int
	err := r.pool.QueryRow(ctx,
		`SELECT id FROM quests WHERE game_id = $1 AND quest_key = $2`,
		gameID, questKey,
	).Scan(&id)
	if err == pgx.ErrNoRows {
		return 0, nil
	}
	return id, err
}

func (r *QuestRepo) GetStageIDByKey(ctx context.Context, questID int, stageKey string) (int, error) {
	var id int
	err := r.pool.QueryRow(ctx,
		`SELECT id FROM quest_stages WHERE quest_id = $1 AND stage_key = $2`,
		questID, stageKey,
	).Scan(&id)
	if err == pgx.ErrNoRows {
		return 0, nil
	}
	return id, err
}

// GetPlaythroughQuestStatuses returns a map of quest_key -> status for diffing.
func (r *QuestRepo) GetPlaythroughQuestStatuses(ctx context.Context, playthroughID, gameID int) (map[string]string, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT q.quest_key, pq.status
		FROM playthrough_quests pq
		JOIN quests q ON q.id = pq.quest_id
		WHERE pq.playthrough_id = $1 AND q.game_id = $2`,
		playthroughID, gameID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[string]string)
	for rows.Next() {
		var key, status string
		if err := rows.Scan(&key, &status); err != nil {
			return nil, err
		}
		result[key] = status
	}
	return result, rows.Err()
}

// GetQuestNameByKey returns the display name of a quest.
func (r *QuestRepo) GetQuestNameByKey(ctx context.Context, gameID int, questKey string) (string, error) {
	var name string
	err := r.pool.QueryRow(ctx,
		`SELECT name FROM quests WHERE game_id = $1 AND quest_key = $2`,
		gameID, questKey,
	).Scan(&name)
	if err == pgx.ErrNoRows {
		return questKey, nil
	}
	return name, err
}

func (r *QuestRepo) DeletePlaythroughState(ctx context.Context, tx pgx.Tx, playthroughID int) error {
	_, err := tx.Exec(ctx,
		`DELETE FROM playthrough_stages WHERE playthrough_id = $1`,
		playthroughID,
	)
	if err != nil {
		return err
	}
	_, err = tx.Exec(ctx,
		`DELETE FROM playthrough_quests WHERE playthrough_id = $1`,
		playthroughID,
	)
	return err
}

func (r *QuestRepo) InsertPlaythroughQuest(ctx context.Context, tx pgx.Tx, playthroughID, questID int, status string) error {
	_, err := tx.Exec(ctx,
		`INSERT INTO playthrough_quests (playthrough_id, quest_id, status) VALUES ($1, $2, $3)`,
		playthroughID, questID, status,
	)
	return err
}

func (r *QuestRepo) InsertPlaythroughStage(ctx context.Context, tx pgx.Tx, playthroughID, stageID int, completed bool) error {
	_, err := tx.Exec(ctx,
		`INSERT INTO playthrough_stages (playthrough_id, stage_id, completed) VALUES ($1, $2, $3)`,
		playthroughID, stageID, completed,
	)
	return err
}

func (r *QuestRepo) BeginTx(ctx context.Context) (pgx.Tx, error) {
	return r.pool.Begin(ctx)
}

func (r *QuestRepo) ListByPlaythrough(ctx context.Context, playthroughID, gameID int) ([]model.QuestWithStatus, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT
			q.id,
			q.quest_key,
			q.name,
			q.category,
			q.location,
			COALESCE(pq.status, 'unstarted') AS status,
			COALESCE(stage_counts.completed, 0) AS stages_completed,
			COALESCE(stage_counts.total, 0) AS stages_total
		FROM quests q
		LEFT JOIN playthrough_quests pq ON pq.quest_id = q.id AND pq.playthrough_id = $1
		LEFT JOIN LATERAL (
			SELECT
				COUNT(*) AS total,
				COUNT(*) FILTER (WHERE ps.completed = true) AS completed
			FROM quest_stages qs
			LEFT JOIN playthrough_stages ps ON ps.stage_id = qs.id AND ps.playthrough_id = $1
			WHERE qs.quest_id = q.id
		) stage_counts ON true
		WHERE q.game_id = $2
		ORDER BY q.sort_order, q.name`,
		playthroughID, gameID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var quests []model.QuestWithStatus
	for rows.Next() {
		var q model.QuestWithStatus
		if err := rows.Scan(&q.ID, &q.QuestKey, &q.Name, &q.Category, &q.Location, &q.Status, &q.StagesCompleted, &q.StagesTotal); err != nil {
			return nil, err
		}
		quests = append(quests, q)
	}
	return quests, rows.Err()
}

func (r *QuestRepo) GetDetail(ctx context.Context, playthroughID, questID int) (*model.QuestDetail, error) {
	var qd model.QuestDetail
	err := r.pool.QueryRow(ctx, `
		SELECT
			q.id, q.quest_key, q.name, q.description, q.category, q.location,
			COALESCE(pq.status, 'unstarted'),
			q.guide_content
		FROM quests q
		LEFT JOIN playthrough_quests pq ON pq.quest_id = q.id AND pq.playthrough_id = $1
		WHERE q.id = $2`,
		playthroughID, questID,
	).Scan(&qd.ID, &qd.QuestKey, &qd.Name, &qd.Description, &qd.Category, &qd.Location, &qd.Status, &qd.GuideContent)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	stageRows, err := r.pool.Query(ctx, `
		SELECT qs.stage_key, qs.name, COALESCE(ps.completed, false), qs.sort_order
		FROM quest_stages qs
		LEFT JOIN playthrough_stages ps ON ps.stage_id = qs.id AND ps.playthrough_id = $1
		WHERE qs.quest_id = $2
		ORDER BY qs.sort_order`,
		playthroughID, questID,
	)
	if err != nil {
		return nil, err
	}
	defer stageRows.Close()

	for stageRows.Next() {
		var s model.StageDetail
		if err := stageRows.Scan(&s.StageKey, &s.Name, &s.Completed, &s.SortOrder); err != nil {
			return nil, err
		}
		qd.Stages = append(qd.Stages, s)
	}
	if qd.Stages == nil {
		qd.Stages = []model.StageDetail{}
	}

	return &qd, stageRows.Err()
}
