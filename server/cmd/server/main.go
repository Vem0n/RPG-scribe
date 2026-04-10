package main

import (
	"context"
	"io/fs"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"

	server "github.com/rpg-scribe/server"
	"github.com/rpg-scribe/server/internal/config"
	"github.com/rpg-scribe/server/internal/database"
	"github.com/rpg-scribe/server/internal/handler"
	"github.com/rpg-scribe/server/internal/repository"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("loading config: %v", err)
	}

	log.Println("running database migrations...")
	if err := database.RunMigrations(cfg.DatabaseURL); err != nil {
		log.Fatalf("running migrations: %v", err)
	}
	log.Println("migrations complete")

	ctx := context.Background()
	pool, err := database.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("connecting to database: %v", err)
	}
	defer pool.Close()

	r := setupRouter(cfg, pool)

	srv := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: r,
	}

	go func() {
		log.Printf("server listening on :%s", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("shutting down server...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("server shutdown error: %v", err)
	}
	log.Println("server stopped")
}

func setupRouter(cfg *config.Config, pool *pgxpool.Pool) *gin.Engine {
	if !cfg.IsDev() {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "X-API-Key", "Authorization"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	userRepo := repository.NewUserRepo(pool)
	gameRepo := repository.NewGameRepo(pool)
	playthroughRepo := repository.NewPlaythroughRepo(pool)
	questRepo := repository.NewQuestRepo(pool)

	wsHub := handler.NewWSHub()
	syncHandler := handler.NewSyncHandler(userRepo, gameRepo, playthroughRepo, questRepo, wsHub)
	userHandler := handler.NewUserHandler(userRepo)
	gameHandler := handler.NewGameHandler(gameRepo)
	playthroughHandler := handler.NewPlaythroughHandler(playthroughRepo, questRepo)
	questHandler := handler.NewQuestHandler(questRepo)
	authHandler := handler.NewAuthHandler(userRepo)

	v1 := r.Group("/api/v1")
	{
		v1.GET("/health", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{"status": "ok"})
		})

		v1.POST("/sync", handler.APIKeyAuth(cfg.APIKey), syncHandler.Sync)

		v1.POST("/auth/login", authHandler.Login)

		v1.GET("/users", userHandler.List)
		v1.GET("/users/:username/playthroughs", playthroughHandler.ListByUser)
		v1.GET("/playthroughs/:id", playthroughHandler.Get)
		v1.GET("/playthroughs/:id/quests/:questId", questHandler.GetDetail)
		v1.GET("/games", gameHandler.List)
		v1.GET("/ws", wsHub.ServeWS)
	}

	if !cfg.IsDev() {
		staticFS, err := fs.Sub(server.StaticFS, "static")
		if err != nil {
			log.Fatalf("static fs: %v", err)
		}
		fileServer := http.FileServer(http.FS(staticFS))
		indexHTML, err := fs.ReadFile(staticFS, "index.html")
		if err != nil {
			log.Fatalf("reading index.html: %v", err)
		}
		r.NoRoute(func(c *gin.Context) {
			path := c.Request.URL.Path
			// Try to serve static file first
			if f, err := staticFS.(fs.ReadFileFS).ReadFile(path[1:]); err == nil {
				_ = f
				fileServer.ServeHTTP(c.Writer, c.Request)
				return
			}
			// SPA fallback: serve index.html for all other routes
			c.Data(http.StatusOK, "text/html; charset=utf-8", indexHTML)
		})
	}

	return r
}
