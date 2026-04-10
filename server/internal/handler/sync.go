package handler

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/model"
	"github.com/rpg-scribe/server/internal/repository"
)

type SyncHandler struct {
	users        *repository.UserRepo
	games        *repository.GameRepo
	playthroughs *repository.PlaythroughRepo
	quests       *repository.QuestRepo
	ws           *WSHub
	// Per-playthrough mutex to prevent concurrent syncs deadlocking
	syncLocks sync.Map // key: "user_id:game_id:external_id" -> *sync.Mutex
}

func NewSyncHandler(users *repository.UserRepo, games *repository.GameRepo, playthroughs *repository.PlaythroughRepo, quests *repository.QuestRepo, ws *WSHub) *SyncHandler {
	return &SyncHandler{users: users, games: games, playthroughs: playthroughs, quests: quests, ws: ws}
}

func (h *SyncHandler) getSyncLock(key string) *sync.Mutex {
	val, _ := h.syncLocks.LoadOrStore(key, &sync.Mutex{})
	return val.(*sync.Mutex)
}

func (h *SyncHandler) Sync(c *gin.Context) {
	var req model.SyncRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Basic validation
	if req.Username == "" || req.GameSlug == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username and game_slug are required"})
		return
	}
	if req.Playthrough.ExternalID == "" || req.Playthrough.Name == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "playthrough external_id and name are required"})
		return
	}

	ctx := c.Request.Context()

	user, err := h.users.FindOrCreate(ctx, req.Username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to find or create user"})
		log.Printf("find or create user: %v", err)
		return
	}

	game, err := h.games.GetBySlug(ctx, req.GameSlug)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to look up game"})
		log.Printf("get game by slug: %v", err)
		return
	}
	if game == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "unknown game slug: " + req.GameSlug})
		return
	}

	playthrough, err := h.playthroughs.FindOrCreate(ctx, user.ID, game.ID, req.Playthrough.ExternalID, req.Playthrough.Name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to find or create playthrough"})
		log.Printf("find or create playthrough: %v", err)
		return
	}

	// Serialize syncs for the same playthrough — prevents deadlocks
	// when autosave + quicksave trigger near-simultaneously
	lockKey := fmt.Sprintf("%d:%d:%s", user.ID, game.ID, req.Playthrough.ExternalID)
	mu := h.getSyncLock(lockKey)
	mu.Lock()
	defer mu.Unlock()

	// Use a timeout context so a stuck transaction can't hold the lock forever
	ctx, cancel := context.WithTimeout(c.Request.Context(), 30*time.Second)
	defer cancel()

	// Snapshot old quest statuses for diffing
	oldStatuses, err := h.quests.GetPlaythroughQuestStatuses(ctx, playthrough.ID, game.ID)
	if err != nil {
		log.Printf("warning: failed to snapshot old statuses: %v", err)
		oldStatuses = make(map[string]string)
	}

	tx, err := h.quests.BeginTx(ctx)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to begin transaction"})
		log.Printf("begin tx: %v", err)
		return
	}
	defer tx.Rollback(ctx)

	if err := h.quests.DeletePlaythroughState(ctx, tx, playthrough.ID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to clear playthrough state"})
		log.Printf("delete playthrough state: %v", err)
		return
	}

	questsSynced := 0
	stagesSynced := 0

	// Track new statuses for diffing
	newStatuses := make(map[string]string)

	for _, sq := range req.Quests {
		questID, err := h.quests.GetQuestIDByKey(ctx, game.ID, sq.QuestKey)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to look up quest"})
			log.Printf("get quest by key: %v", err)
			return
		}
		if questID == 0 {
			log.Printf("warning: unknown quest_key %q for game %q, skipping", sq.QuestKey, req.GameSlug)
			continue
		}

		if err := h.quests.InsertPlaythroughQuest(ctx, tx, playthrough.ID, questID, sq.Status); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to insert quest state"})
			log.Printf("insert playthrough quest: %v", err)
			return
		}
		questsSynced++
		newStatuses[sq.QuestKey] = sq.Status

		for _, ss := range sq.Stages {
			stageID, err := h.quests.GetStageIDByKey(ctx, questID, ss.StageKey)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to look up stage"})
				log.Printf("get stage by key: %v", err)
				return
			}
			if stageID == 0 {
				log.Printf("warning: unknown stage_key %q for quest %q, skipping", ss.StageKey, sq.QuestKey)
				continue
			}

			if err := h.quests.InsertPlaythroughStage(ctx, tx, playthrough.ID, stageID, ss.Completed); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to insert stage state"})
				log.Printf("insert playthrough stage: %v", err)
				return
			}
			stagesSynced++
		}
	}

	if err := tx.Commit(ctx); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to commit transaction"})
		log.Printf("commit tx: %v", err)
		return
	}

	if err := h.playthroughs.UpdateLastSynced(ctx, playthrough.ID); err != nil {
		log.Printf("warning: failed to update last_synced_at: %v", err)
	}

	// Pre-resolve quest names while we still have the request context
	// (avoids DB pool contention from the goroutine)
	questNames := make(map[string]string)
	for questKey, newStatus := range newStatuses {
		oldStatus := oldStatuses[questKey]
		if oldStatus == newStatus || newStatus == "unstarted" || len(oldStatuses) == 0 {
			continue
		}
		name, err := h.quests.GetQuestNameByKey(ctx, game.ID, questKey)
		if err != nil {
			name = questKey
		}
		questNames[questKey] = name
	}

	// Emit quest change events via WebSocket (no DB calls in goroutine)
	go h.emitChanges(req.Username, game, oldStatuses, newStatuses, questNames)
	h.ws.Emit("sync-complete", map[string]interface{}{
		"username":       req.Username,
		"game_slug":      game.Slug,
		"game_name":      game.Name,
		"playthrough_id": playthrough.ID,
		"quests_synced":  questsSynced,
		"stages_synced":  stagesSynced,
	})

	c.JSON(http.StatusOK, model.SyncResponse{
		Status:        "ok",
		PlaythroughID: playthrough.ID,
		QuestsSynced:  questsSynced,
		StagesSynced:  stagesSynced,
	})
}

func (h *SyncHandler) emitChanges(username string, game *model.Game, oldStatuses, newStatuses map[string]string, questNames map[string]string) {
	emitted := 0
	for questKey, newStatus := range newStatuses {
		oldStatus := oldStatuses[questKey]
		if oldStatus == newStatus || newStatus == "unstarted" || len(oldStatuses) == 0 {
			continue
		}

		questName := questNames[questKey]
		if questName == "" {
			questName = questKey
		}

		log.Printf("quest-change: %s %s->%s (%s)", questKey, oldStatus, newStatus, questName)
		h.ws.Emit("quest-change", QuestChangeEvent{
			Username:  username,
			GameName:  game.Name,
			GameSlug:  game.Slug,
			QuestName: questName,
			OldStatus: oldStatus,
			NewStatus: newStatus,
		})
		emitted++
	}
	log.Printf("emitChanges: %d events emitted", emitted)
}
