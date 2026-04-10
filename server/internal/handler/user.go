package handler

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/model"
	"github.com/rpg-scribe/server/internal/repository"
)

type UserHandler struct {
	users *repository.UserRepo
}

func NewUserHandler(users *repository.UserRepo) *UserHandler {
	return &UserHandler{users: users}
}

func (h *UserHandler) List(c *gin.Context) {
	users, err := h.users.List(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list users"})
		log.Printf("list users: %v", err)
		return
	}
	if users == nil {
		users = []model.User{}
	}
	c.JSON(http.StatusOK, gin.H{"users": users})
}
