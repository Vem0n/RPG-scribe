import { useEffect, useRef } from "react";
import { toast } from "sonner";

export interface QuestChangeEvent {
  username: string;
  game_name: string;
  game_slug: string;
  quest_name: string;
  old_status: string;
  new_status: string;
}

export interface SyncCompleteEvent {
  username: string;
  game_slug: string;
  game_name: string;
  playthrough_id: number;
  quests_synced: number;
  stages_synced: number;
}

interface WSMessage {
  type: string;
  data: unknown;
}

const STATUS_LABELS: Record<string, string> = {
  started: "started",
  finished: "completed",
  failed: "failed",
};

const STATUS_EMOJI: Record<string, string> = {
  started: "🗡️",
  finished: "✅",
  failed: "💀",
};

// Global listeners for sync-complete events
type SyncListener = (event: SyncCompleteEvent) => void;
const syncListeners = new Set<SyncListener>();

export function onSyncComplete(listener: SyncListener) {
  syncListeners.add(listener);
  return () => { syncListeners.delete(listener); };
}

function getWSUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // In dev, Vite proxies /api but not /ws — connect directly to backend
  const host = window.location.hostname;
  const port = import.meta.env.DEV ? "8081" : window.location.port;
  return `${proto}//${host}:${port}/api/v1/ws?role=web`;
}

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  const url = getWSUrl();
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("[ws] connected");
    // Identify ourselves
    ws!.send(JSON.stringify({
      type: "identify",
      data: { role: "web", username: "" },
    }));
  };

  ws.onmessage = (event) => {
    try {
      const msg: WSMessage = JSON.parse(event.data);
      handleMessage(msg);
    } catch {}
  };

  ws.onclose = () => {
    console.log("[ws] disconnected, reconnecting in 3s...");
    ws = null;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    ws?.close();
  };
}

function handleMessage(msg: WSMessage) {
  switch (msg.type) {
    case "quest-change": {
      const data = msg.data as QuestChangeEvent;
      const verb = STATUS_LABELS[data.new_status] || data.new_status;
      const emoji = STATUS_EMOJI[data.new_status] || "📋";
      toast(`${emoji} ${data.username} ${verb} "${data.quest_name}"`, {
        id: `qc-${data.quest_name}-${Date.now()}-${Math.random()}`,
        description: data.game_name,
        duration: 5000,
      });
      break;
    }
    case "sync-complete": {
      const data = msg.data as SyncCompleteEvent;
      for (const listener of syncListeners) {
        listener(data);
      }
      break;
    }
    case "pong":
      break;
  }
}

export function useQuestEvents() {
  useEffect(() => {
    connect();
    return () => {
      // Don't disconnect on unmount — keep the singleton alive
    };
  }, []);
}

/**
 * Hook for pages to auto-refresh when a sync completes.
 */
export function useSyncRefresh(refetch: () => void, filter?: { playthroughId?: number; username?: string }) {
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  useEffect(() => {
    return onSyncComplete((event) => {
      if (filter?.playthroughId && event.playthrough_id !== filter.playthroughId) return;
      if (filter?.username && event.username !== filter.username) return;
      refetchRef.current();
    });
  }, [filter?.playthroughId, filter?.username]);
}
