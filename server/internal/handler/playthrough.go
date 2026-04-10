package handler

import (
	"log"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/model"
	"github.com/rpg-scribe/server/internal/repository"
)

type PlaythroughHandler struct {
	playthroughs *repository.PlaythroughRepo
	quests       *repository.QuestRepo
}

func NewPlaythroughHandler(playthroughs *repository.PlaythroughRepo, quests *repository.QuestRepo) *PlaythroughHandler {
	return &PlaythroughHandler{playthroughs: playthroughs, quests: quests}
}

func (h *PlaythroughHandler) ListByUser(c *gin.Context) {
	username := c.Param("username")

	playthroughs, err := h.playthroughs.ListByUser(c.Request.Context(), username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list playthroughs"})
		log.Printf("list playthroughs by user: %v", err)
		return
	}

	c.JSON(http.StatusOK, gin.H{"playthroughs": playthroughs})
}

func (h *PlaythroughHandler) Get(c *gin.Context) {
	id, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid playthrough id"})
		return
	}

	ctx := c.Request.Context()

	pw, err := h.playthroughs.GetByIDWithGame(ctx, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get playthrough"})
		log.Printf("get playthrough: %v", err)
		return
	}
	if pw == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "playthrough not found"})
		return
	}

	quests, err := h.quests.ListByPlaythrough(ctx, pw.ID, pw.GameID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list quests"})
		log.Printf("list quests by playthrough: %v", err)
		return
	}
	if quests == nil {
		quests = []model.QuestWithStatus{}
	}

	c.JSON(http.StatusOK, gin.H{
		"playthrough": pw.Playthrough,
		"game":        pw.Game,
		"quests":      quests,
	})
}
