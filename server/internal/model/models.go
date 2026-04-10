package model

import "time"

type User struct {
	ID             int        `json:"id"`
	Username       string     `json:"username"`
	Password       *string    `json:"-"`
	CreatedAt      time.Time  `json:"created_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
	LastGameSlug   *string    `json:"last_game_slug,omitempty"`
	LastGameName   *string    `json:"last_game_name,omitempty"`
}

type Game struct {
	ID        int       `json:"id"`
	Slug      string    `json:"slug"`
	Name      string    `json:"name"`
	CreatedAt time.Time `json:"created_at"`
}

type Quest struct {
	ID           int     `json:"id"`
	GameID       int     `json:"game_id"`
	QuestKey     string  `json:"quest_key"`
	Name         string  `json:"name"`
	Description  *string `json:"description,omitempty"`
	Category     *string `json:"category,omitempty"`
	Location     *string `json:"location,omitempty"`
	SortOrder    int     `json:"sort_order"`
	GuideContent *string `json:"guide_content,omitempty"`
}

type QuestStage struct {
	ID        int    `json:"id"`
	QuestID   int    `json:"quest_id"`
	StageKey  string `json:"stage_key"`
	Name      string `json:"name"`
	SortOrder int    `json:"sort_order"`
}

type Playthrough struct {
	ID           int        `json:"id"`
	UserID       int        `json:"user_id"`
	GameID       int        `json:"game_id"`
	Name         string     `json:"name"`
	ExternalID   *string    `json:"external_id,omitempty"`
	LastSyncedAt *time.Time `json:"last_synced_at,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
	UpdatedAt    time.Time  `json:"updated_at"`
}

type PlaythroughQuest struct {
	ID             int       `json:"id"`
	PlaythroughID  int       `json:"playthrough_id"`
	QuestID        int       `json:"quest_id"`
	Status         string    `json:"status"`
	UpdatedAt      time.Time `json:"updated_at"`
}

type PlaythroughStage struct {
	ID             int  `json:"id"`
	PlaythroughID  int  `json:"playthrough_id"`
	StageID        int  `json:"stage_id"`
	Completed      bool `json:"completed"`
}

// API response types

type PlaythroughWithGame struct {
	Playthrough
	Game         Game         `json:"game"`
	QuestSummary QuestSummary `json:"quest_summary"`
}

type QuestSummary struct {
	Total     int `json:"total"`
	Finished  int `json:"finished"`
	Started   int `json:"started"`
	Failed    int `json:"failed"`
	Unstarted int `json:"unstarted"`
}

type QuestWithStatus struct {
	ID              int     `json:"quest_id"`
	QuestKey        string  `json:"quest_key"`
	Name            string  `json:"name"`
	Category        *string `json:"category,omitempty"`
	Location        *string `json:"location,omitempty"`
	Status          string  `json:"status"`
	StagesCompleted int     `json:"stages_completed"`
	StagesTotal     int     `json:"stages_total"`
}

type QuestDetail struct {
	ID           int            `json:"id"`
	QuestKey     string         `json:"quest_key"`
	Name         string         `json:"name"`
	Description  *string        `json:"description,omitempty"`
	Category     *string        `json:"category,omitempty"`
	Location     *string        `json:"location,omitempty"`
	Status       string         `json:"status"`
	GuideContent *string        `json:"guide_content,omitempty"`
	Stages       []StageDetail  `json:"stages"`
}

type StageDetail struct {
	StageKey  string `json:"stage_key"`
	Name      string `json:"name"`
	Completed bool   `json:"completed"`
	SortOrder int    `json:"sort_order"`
}

// Sync request types

type SyncRequest struct {
	Username    string             `json:"username" binding:"required"`
	GameSlug    string             `json:"game_slug" binding:"required"`
	Playthrough SyncPlaythrough    `json:"playthrough" binding:"required"`
	Quests      []SyncQuest        `json:"quests"`
}

type SyncPlaythrough struct {
	ExternalID string `json:"external_id" binding:"required"`
	Name       string `json:"name" binding:"required"`
}

type SyncQuest struct {
	QuestKey string      `json:"quest_key" binding:"required"`
	Status   string      `json:"status" binding:"required"`
	Stages   []SyncStage `json:"stages"`
}

type SyncStage struct {
	StageKey  string `json:"stage_key" binding:"required"`
	Completed bool   `json:"completed"`
}

type SyncResponse struct {
	Status        string `json:"status"`
	PlaythroughID int    `json:"playthrough_id"`
	QuestsSynced  int    `json:"quests_synced"`
	StagesSynced  int    `json:"stages_synced"`
}
