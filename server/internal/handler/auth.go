package handler

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/rpg-scribe/server/internal/repository"
	"golang.org/x/crypto/bcrypt"
)

type AuthHandler struct {
	users *repository.UserRepo
}

func NewAuthHandler(users *repository.UserRepo) *AuthHandler {
	return &AuthHandler{users: users}
}

type loginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password"`
}

func (h *AuthHandler) Login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	user, err := h.users.GetByUsername(c.Request.Context(), req.Username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to look up user"})
		log.Printf("get user by username: %v", err)
		return
	}
	if user == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
		return
	}

	if user.Password != nil && *user.Password != "" {
		if err := bcrypt.CompareHashAndPassword([]byte(*user.Password), []byte(req.Password)); err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid password"})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"ok":   true,
		"user": user,
	})
}
