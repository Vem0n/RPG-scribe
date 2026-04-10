package handler

import (
	"log"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/repository"
)

type QuestHandler struct {
	quests *repository.QuestRepo
}

func NewQuestHandler(quests *repository.QuestRepo) *QuestHandler {
	return &QuestHandler{quests: quests}
}

func (h *QuestHandler) GetDetail(c *gin.Context) {
	playthroughID, err := strconv.Atoi(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid playthrough id"})
		return
	}

	questID, err := strconv.Atoi(c.Param("questId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid quest id"})
		return
	}

	detail, err := h.quests.GetDetail(c.Request.Context(), playthroughID, questID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get quest detail"})
		log.Printf("get quest detail: %v", err)
		return
	}
	if detail == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "quest not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"quest": detail})
}
