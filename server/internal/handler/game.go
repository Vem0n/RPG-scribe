package handler

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/model"
	"github.com/rpg-scribe/server/internal/repository"
)

type GameHandler struct {
	games *repository.GameRepo
}

func NewGameHandler(games *repository.GameRepo) *GameHandler {
	return &GameHandler{games: games}
}

func (h *GameHandler) List(c *gin.Context) {
	games, err := h.games.List(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list games"})
		log.Printf("list games: %v", err)
		return
	}
	if games == nil {
		games = []model.Game{}
	}
	c.JSON(http.StatusOK, gin.H{"games": games})
}
