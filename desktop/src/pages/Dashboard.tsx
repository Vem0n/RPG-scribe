import { useState, useEffect, useCallback, useRef } from "react";
import { SUPPORTED_GAMES, type GameConfig } from "../games";
import { saveConfig, type AppConfig, type GameState, getActiveUser, getEnabledGames } from "../store";
import GameSetup from "../components/GameSetup";

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

interface LogEntry {
  time: string;
  level: "info" | "error" | "success" | "warn";
  game?: string;
  message: string;
}

interface DashboardProps {
  config: AppConfig;
  setConfig: (c: AppConfig) => void;
}

export default function Dashboard({ config, setConfig }: DashboardProps) {
  const [settingUp, setSettingUp] = useState<GameConfig | null>(null);
  const [syncingGame, setSyncingGame] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [tab, setTab] = useState<"games" | "logs">("games");
  const [logFilter, setLogFilter] = useState<"all" | "error" | "success" | "info">("all");
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [editingServer, setEditingServer] = useState(false);
  const [serverDraft, setServerDraft] = useState(config.serverUrl);
  const [editingApiKey, setEditingApiKey] = useState(false);
  const [apiKeyDraft, setApiKeyDraft] = useState(config.apiKey);

  const activeUser = getActiveUser(config);
  const enabledGames = activeUser.enabledGames;

  const addLog = useCallback((level: LogEntry["level"], message: string, game?: string) => {
    setLogs((prev) => [...prev.slice(-200), {
      time: new Date().toLocaleTimeString(),
      level,
      game,
      message,
    }]);
  }, []);

  // Listen for save-changed events from Rust watcher
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    async function setup() {
      if (!window.__TAURI_INTERNALS__) return;
      try {
        const { listen } = await import("@tauri-apps/api/event");
        unlisten = await listen<{ game_id: string; path: string }>(
          "save-changed",
          async (event) => {
            const { game_id, path } = event.payload;
            const game = SUPPORTED_GAMES.find((g) => g.id === game_id);
            addLog("info", `Save change detected: ${path.split(/[/\\]/).pop()}`, game?.name);
            await runSync(game_id, path);
          }
        );
      } catch {}
    }
    setup();
    return () => unlisten?.();
  }, [config]);

  async function runSync(gameId: string, savePath: string) {
    const game = SUPPORTED_GAMES.find((g) => g.id === gameId);
    const state = enabledGames[gameId];
    if (!game || !state) return;
    setSyncingGame(gameId);
    addLog("info", "Syncing...", game.name);
    try {
      if (window.__TAURI_INTERNALS__) {
        const { invoke } = await import("@tauri-apps/api/core");
        const result = await invoke<string>("run_scraper", {
          scriptPath: game.scraperScript,
          savePath: savePath || state.savePath,
          serverUrl: config.serverUrl,
          username: config.activeUser,
          apiKey: config.apiKey,
        });
        const lastLine = result.trim().split("\n").pop() || "OK";
        addLog("success", lastLine, game.name);
        await updateGameState(gameId, { lastSyncStatus: "success", lastSyncTime: new Date().toISOString(), lastSyncMessage: undefined });
      }
    } catch (e: any) {
      const errMsg = String(e).replace(/\\n/g, "\n").slice(0, 500);
      addLog("error", errMsg, game.name);
      await updateGameState(gameId, { lastSyncStatus: "error", lastSyncTime: new Date().toISOString(), lastSyncMessage: errMsg });
    }
    setSyncingGame(null);
  }

  async function updateGameState(gameId: string, partial: Partial<GameState>) {
    const user = getActiveUser(config);
    const updatedUser = { ...user, enabledGames: { ...user.enabledGames, [gameId]: { ...user.enabledGames[gameId], ...partial } } };
    const updated = { ...config, users: { ...config.users, [config.activeUser]: updatedUser } };
    await saveConfig(updated);
    setConfig(updated);
  }

  async function toggleGame(game: GameConfig) {
    const state = enabledGames[game.id];
    if (state?.enabled) {
      if (window.__TAURI_INTERNALS__) {
        try { const { invoke } = await import("@tauri-apps/api/core"); await invoke("stop_watching", { gameId: game.id }); } catch {}
      }
      const user = getActiveUser(config);
      const newGames = { ...user.enabledGames };
      delete newGames[game.id];
      const updated = { ...config, users: { ...config.users, [config.activeUser]: { ...user, enabledGames: newGames } } };
      await saveConfig(updated);
      setConfig(updated);
      addLog("info", `Disabled`, game.name);
    } else {
      setSettingUp(game);
    }
  }

  async function completeSetup(game: GameConfig, state: GameState) {
    const user = getActiveUser(config);
    const updatedUser = { ...user, enabledGames: { ...user.enabledGames, [game.id]: state } };
    const updated = { ...config, users: { ...config.users, [config.activeUser]: updatedUser } };
    await saveConfig(updated);
    setConfig(updated);
    setSettingUp(null);
    addLog("success", `Enabled — watching ${state.savePath}`, game.name);
    if (window.__TAURI_INTERNALS__) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("start_watching", { gameId: game.id, savePath: state.savePath, playthrough: state.selectedPlaythrough || null });
        addLog("info", "Watcher started", game.name);
      } catch (e) { addLog("error", `Watcher failed: ${e}`, game.name); }
    }
  }

  useEffect(() => {
    async function restoreWatchers() {
      if (!window.__TAURI_INTERNALS__) return;
      const { invoke } = await import("@tauri-apps/api/core");
      for (const [gameId, state] of Object.entries(enabledGames)) {
        if (!state.enabled) continue;
        const game = SUPPORTED_GAMES.find((g) => g.id === gameId);
        try {
          await invoke("start_watching", { gameId, savePath: state.savePath, playthrough: state.selectedPlaythrough || null });
          addLog("info", "Watcher restored", game?.name);
        } catch {}
      }
    }
    restoreWatchers();
  }, []);

  if (settingUp) {
    return <GameSetup game={settingUp} config={config} onComplete={(state) => completeSetup(settingUp, state)} onCancel={() => setSettingUp(null)} />;
  }

  const activeCount = Object.values(enabledGames).filter((g) => g.enabled).length;
  const errorCount = logs.filter((l) => l.level === "error").length;
  const filteredLogs = logFilter === "all" ? logs : logs.filter((l) => l.level === logFilter);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div data-tauri-drag-region style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--border-subtle)" }} className="shrink-0 flex items-center justify-between px-5 h-12">
        <div className="flex items-center gap-2.5">
          <span className="text-lg">📜</span>
          <span className="text-sm font-bold tracking-wide">RPG Scribe</span>
        </div>
        <div className="flex items-center gap-3" style={{ fontSize: 11 }}>
          {/* Editable server URL */}
          {editingServer ? (
            <form className="flex items-center gap-1" onSubmit={async (e) => {
              e.preventDefault();
              const updated = { ...config, serverUrl: serverDraft };
              await saveConfig(updated);
              setConfig(updated);
              setEditingServer(false);
            }}>
              <input
                autoFocus
                value={serverDraft}
                onChange={(e) => setServerDraft(e.target.value)}
                onBlur={() => setEditingServer(false)}
                className="px-1.5 py-0.5 rounded text-[11px] w-40"
                style={{ background: "var(--bg-tertiary)", border: "1px solid var(--accent)", color: "var(--text-primary)" }}
              />
            </form>
          ) : (
            <button
              onClick={() => { setServerDraft(config.serverUrl); setEditingServer(true); }}
              className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
              style={{ color: "var(--text-muted)" }}
              title="Click to change server URL"
            >
              <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: "var(--success)" }} />
              {config.serverUrl}
            </button>
          )}

          {/* Editable API key */}
          {editingApiKey ? (
            <form className="flex items-center gap-1" onSubmit={async (e) => {
              e.preventDefault();
              const updated = { ...config, apiKey: apiKeyDraft };
              await saveConfig(updated);
              setConfig(updated);
              setEditingApiKey(false);
            }}>
              <input
                autoFocus
                type="password"
                value={apiKeyDraft}
                onChange={(e) => setApiKeyDraft(e.target.value)}
                onBlur={() => setEditingApiKey(false)}
                className="px-1.5 py-0.5 rounded text-[11px] w-40"
                style={{ background: "var(--bg-tertiary)", border: "1px solid var(--accent)", color: "var(--text-primary)" }}
              />
            </form>
          ) : (
            <button
              onClick={() => { setApiKeyDraft(config.apiKey); setEditingApiKey(true); }}
              className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
              style={{ color: "var(--text-muted)" }}
              title="Click to change API key"
            >
              API Key: {config.apiKey ? "••••••••" : "Not set"}
            </button>
          )}

          {/* User switcher */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-1 px-2 py-1 rounded hover:opacity-80 transition-opacity"
              style={{ color: "var(--accent)", background: "var(--accent-dim)" }}
            >
              {config.activeUser}
              <span style={{ fontSize: 8 }}>▼</span>
            </button>

            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 min-w-48 rounded-lg overflow-hidden shadow-xl"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-color)" }}>
                  {/* Existing users */}
                  {Object.keys(config.users).map((username) => (
                    <button
                      key={username}
                      onClick={async () => {
                        const updated = { ...config, activeUser: username };
                        await saveConfig(updated);
                        setConfig(updated);
                        setShowUserMenu(false);
                        addLog("info", `Switched to user: ${username}`);
                      }}
                      className="w-full text-left px-3 py-2 text-xs flex items-center justify-between transition-colors"
                      style={{
                        color: username === config.activeUser ? "var(--accent)" : "var(--text-primary)",
                        background: username === config.activeUser ? "var(--accent-dim)" : "transparent",
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = "var(--accent-dim)"}
                      onMouseLeave={(e) => e.currentTarget.style.background = username === config.activeUser ? "var(--accent-dim)" : "transparent"}
                    >
                      <span>{username}</span>
                      {username === config.activeUser && <span>✓</span>}
                    </button>
                  ))}

                  {/* Divider */}
                  <div style={{ borderTop: "1px solid var(--border-color)" }} />

                  {/* Add new user */}
                  <form
                    className="flex items-center gap-1 p-2"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!newUsername.trim()) return;
                      const name = newUsername.trim();
                      const updated = {
                        ...config,
                        activeUser: name,
                        users: {
                          ...config.users,
                          [name]: { username: name, enabledGames: {} },
                        },
                      };
                      await saveConfig(updated);
                      setConfig(updated);
                      setNewUsername("");
                      setShowUserMenu(false);
                      addLog("info", `Created and switched to user: ${name}`);
                    }}
                  >
                    <input
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      placeholder="New user..."
                      className="flex-1 px-2 py-1 rounded text-[11px]"
                      style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", color: "var(--text-primary)" }}
                    />
                    <button
                      type="submit"
                      disabled={!newUsername.trim()}
                      className="px-2 py-1 rounded text-[11px] font-medium"
                      style={{ background: "var(--accent)", color: "#fff", opacity: newUsername.trim() ? 1 : 0.4 }}
                    >
                      Add
                    </button>
                  </form>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="shrink-0 flex px-5 gap-1 pt-2" style={{ background: "var(--bg-primary)" }}>
        <TabButton active={tab === "games"} onClick={() => setTab("games")}>
          Games
        </TabButton>
        <TabButton active={tab === "logs"} onClick={() => setTab("logs")} badge={errorCount > 0 ? errorCount : undefined}>
          Logs
        </TabButton>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden" style={{ background: "var(--bg-primary)" }}>
        {tab === "games" ? (
          <GamesTab
            enabledGames={enabledGames}
            syncingGame={syncingGame}
            toggleGame={toggleGame}
          />
        ) : (
          <LogsTab
            logs={filteredLogs}
            allLogs={logs}
            filter={logFilter}
            setFilter={setLogFilter}
            onClear={() => setLogs([])}
          />
        )}
      </div>

      {/* Status bar */}
      <div className="shrink-0 flex items-center justify-between px-5 h-8" style={{ background: "var(--bg-secondary)", borderTop: "1px solid var(--border-subtle)", fontSize: 11, color: "var(--text-muted)" }}>
        <span className="flex items-center gap-1.5">
          {activeCount > 0 && <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: "var(--success)" }} />}
          {activeCount > 0 ? `${activeCount} game${activeCount > 1 ? "s" : ""} active` : "No games enabled"}
        </span>
        <span>{logs.length} log entries</span>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children, badge }: {
  active: boolean; onClick: () => void; children: React.ReactNode; badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className="relative px-4 py-2 text-xs font-semibold rounded-t-lg transition-colors"
      style={{
        background: active ? "var(--bg-tertiary)" : "transparent",
        color: active ? "var(--text-primary)" : "var(--text-muted)",
        borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
      }}
    >
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="absolute -top-1 -right-1 min-w-4 h-4 flex items-center justify-center rounded-full text-[10px] font-bold px-1"
          style={{ background: "var(--danger)", color: "#fff" }}>
          {badge}
        </span>
      )}
    </button>
  );
}

function GamesTab({ enabledGames, syncingGame, toggleGame }: {
  enabledGames: Record<string, GameState>; syncingGame: string | null; toggleGame: (g: GameConfig) => void;
}) {
  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="flex flex-col gap-2.5">
        {SUPPORTED_GAMES.map((game) => {
          const state = enabledGames[game.id];
          const enabled = state?.enabled;
          const isSyncing = syncingGame === game.id;

          return (
            <div
              key={game.id}
              className="flex items-center gap-4 rounded-xl p-4"
              style={{
                background: enabled ? "var(--accent-dim)" : "var(--bg-secondary)",
                border: `1px solid ${enabled ? "rgba(124, 92, 252, 0.25)" : "var(--border-color)"}`,
              }}
            >
              <img src={game.icon} alt={game.name} className="w-10 h-10 shrink-0 rounded-lg object-contain" />
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{game.name}</div>
                {enabled && state ? (
                  <>
                    <div className="text-xs truncate mt-0.5" style={{ color: "var(--text-muted)" }}>
                      📁 {state.savePath}
                      {state.selectedPlaythrough && <span style={{ color: "var(--accent)" }}> / {state.selectedPlaythrough}</span>}
                    </div>
                    {state.lastSyncTime && (
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0" style={{ background: state.lastSyncStatus === "success" ? "var(--success)" : "var(--danger)" }} />
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          {state.lastSyncStatus === "success" ? "Synced" : "Error"} {new Date(state.lastSyncTime).toLocaleTimeString()}
                        </span>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>Not configured</div>
                )}
              </div>
              <button
                onClick={() => toggleGame(game)}
                disabled={isSyncing}
                className="shrink-0 px-4 py-2 rounded-lg text-xs font-semibold"
                style={{
                  background: enabled ? "var(--danger-dim)" : "var(--accent)",
                  color: enabled ? "var(--danger)" : "#fff",
                  border: enabled ? "1px solid rgba(248,113,113,0.2)" : "none",
                  opacity: isSyncing ? 0.5 : 1,
                  boxShadow: enabled ? "none" : "0 4px 12px rgba(124,92,252,0.25)",
                }}
              >
                {isSyncing ? "Syncing..." : enabled ? "Disable" : "Enable"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LogsTab({ logs, allLogs, filter, setFilter, onClear }: {
  logs: LogEntry[]; allLogs: LogEntry[];
  filter: string; setFilter: (f: any) => void; onClear: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, autoScroll]);

  const levelColors: Record<string, string> = {
    info: "var(--text-muted)",
    success: "var(--success)",
    error: "var(--danger)",
    warn: "var(--warning)",
  };

  const levelIcons: Record<string, string> = {
    info: "ℹ️",
    success: "✅",
    error: "❌",
    warn: "⚠️",
  };

  const counts = {
    all: allLogs.length,
    error: allLogs.filter((l) => l.level === "error").length,
    success: allLogs.filter((l) => l.level === "success").length,
    info: allLogs.filter((l) => l.level === "info" || l.level === "warn").length,
  };

  return (
    <div className="h-full flex flex-col">
      {/* Log toolbar */}
      <div className="shrink-0 flex items-center justify-between px-5 py-2 gap-2" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="flex gap-1">
          {(["all", "error", "success", "info"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="px-2.5 py-1 rounded text-[11px] font-medium transition-colors"
              style={{
                background: filter === f ? "var(--accent-dim)" : "transparent",
                color: filter === f ? "var(--accent)" : "var(--text-muted)",
                border: filter === f ? "1px solid rgba(124,92,252,0.2)" : "1px solid transparent",
              }}
            >
              {f === "all" ? "All" : f === "error" ? "Errors" : f === "success" ? "Success" : "Info"}
              {" "}({counts[f]})
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            />
            Auto-scroll
          </label>
          <button
            onClick={onClear}
            className="px-2 py-1 rounded text-[11px]"
            style={{ color: "var(--text-muted)", border: "1px solid var(--border-color)" }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs"
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
          if (!atBottom && autoScroll) setAutoScroll(false);
          if (atBottom && !autoScroll) setAutoScroll(true);
        }}
      >
        {logs.length === 0 ? (
          <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}>
            {allLogs.length === 0 ? "No log entries yet" : "No entries match filter"}
          </div>
        ) : (
          logs.map((entry, i) => (
            <div
              key={i}
              className="flex gap-2 py-1.5 items-start"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <span className="shrink-0 w-16" style={{ color: "var(--text-muted)" }}>{entry.time}</span>
              <span className="shrink-0 w-4 text-center">{levelIcons[entry.level]}</span>
              {entry.game && (
                <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium"
                  style={{ background: "var(--accent-dim)", color: "var(--accent)" }}>
                  {entry.game}
                </span>
              )}
              <span className="flex-1 break-all leading-relaxed" style={{
                color: levelColors[entry.level],
                whiteSpace: entry.level === "error" ? "pre-wrap" : "normal",
              }}>
                {entry.message}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
