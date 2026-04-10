package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

// QuestChangeEvent is emitted when a quest's status changes during sync.
type QuestChangeEvent struct {
	Username  string `json:"username"`
	GameName  string `json:"game_name"`
	GameSlug  string `json:"game_slug"`
	QuestName string `json:"quest_name"`
	OldStatus string `json:"old_status"`
	NewStatus string `json:"new_status"`
}

var upgrader = websocket.Upgrader{
	CheckOrigin:  func(r *http.Request) bool { return true },
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

// WSMessage is the envelope for all WebSocket messages.
type WSMessage struct {
	Type string          `json:"type"`
	Data json.RawMessage `json:"data"`
}

// WSClient represents a connected WebSocket client.
type WSClient struct {
	hub  *WSHub
	conn *websocket.Conn
	send chan []byte
	// Client metadata (set via "identify" message)
	Role     string // "web" or "desktop"
	Username string
}

// WSHub manages all WebSocket connections and broadcasting.
type WSHub struct {
	mu         sync.RWMutex
	clients    map[*WSClient]struct{}
	broadcast  chan []byte
	register   chan *WSClient
	unregister chan *WSClient
}

func NewWSHub() *WSHub {
	h := &WSHub{
		clients:    make(map[*WSClient]struct{}),
		broadcast:  make(chan []byte, 64),
		register:   make(chan *WSClient),
		unregister: make(chan *WSClient),
	}
	go h.run()
	return h
}

func (h *WSHub) run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = struct{}{}
			h.mu.Unlock()
			log.Printf("ws: client connected (role=%s, user=%s), total=%d", client.Role, client.Username, len(h.clients))

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
			log.Printf("ws: client disconnected, total=%d", len(h.clients))

		case msg := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- msg:
				default:
					// Client too slow, disconnect
					close(client.send)
					delete(h.clients, client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

// Emit sends a typed message to all connected clients.
func (h *WSHub) Emit(msgType string, data interface{}) {
	payload, err := json.Marshal(data)
	if err != nil {
		log.Printf("ws: marshal error: %v", err)
		return
	}
	msg := WSMessage{Type: msgType, Data: payload}
	envelope, err := json.Marshal(msg)
	if err != nil {
		return
	}
	h.broadcast <- envelope
}

// EmitTo sends a typed message only to clients matching a filter.
func (h *WSHub) EmitTo(msgType string, data interface{}, filter func(c *WSClient) bool) {
	payload, err := json.Marshal(data)
	if err != nil {
		return
	}
	msg := WSMessage{Type: msgType, Data: payload}
	envelope, err := json.Marshal(msg)
	if err != nil {
		return
	}

	h.mu.RLock()
	defer h.mu.RUnlock()
	for client := range h.clients {
		if filter(client) {
			select {
			case client.send <- envelope:
			default:
			}
		}
	}
}

// ServeWS handles the WebSocket upgrade and connection lifecycle.
func (h *WSHub) ServeWS(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("ws: upgrade error: %v", err)
		return
	}

	client := &WSClient{
		hub:  h,
		conn: conn,
		send: make(chan []byte, 32),
		Role: c.Query("role"),
	}

	h.register <- client

	go client.readPump()
	go client.writePump()
}

func (c *WSClient) readPump() {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("ws: readPump panic recovered: %v", r)
		}
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(4096)
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, raw, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		var msg WSMessage
		if err := json.Unmarshal(raw, &msg); err != nil {
			continue
		}

		// Handle client→server messages
		switch msg.Type {
		case "identify":
			var id struct {
				Role     string `json:"role"`
				Username string `json:"username"`
			}
			json.Unmarshal(msg.Data, &id)
			c.Role = id.Role
			c.Username = id.Username
			log.Printf("ws: client identified as role=%s user=%s", c.Role, c.Username)

		case "ping":
			reply, _ := json.Marshal(WSMessage{Type: "pong", Data: json.RawMessage(`{}`)})
			select {
			case c.send <- reply:
			default:
			}
		}
	}
}

func (c *WSClient) writePump() {
	ticker := time.NewTicker(30 * time.Second)
	defer func() {
		if r := recover(); r != nil {
			log.Printf("ws: writePump panic recovered: %v", r)
		}
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case msg, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
