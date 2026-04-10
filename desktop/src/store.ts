/**
 * Persistent config store for RPG Scribe desktop app.
 * Multi-user support: each user has independent game settings.
 */

export interface UserProfile {
  username: string;
  enabledGames: Record<string, GameState>;
}

export interface GameState {
  enabled: boolean;
  savePath: string;
  selectedPlaythrough?: string;
  lastSyncTime?: string;
  lastSyncStatus?: "success" | "error";
  lastSyncMessage?: string;
}

export interface AppConfig {
  serverUrl: string;
  apiKey: string;
  wizardCompleted: boolean;
  activeUser: string;
  users: Record<string, UserProfile>;
}

// Convenience: get the active user's profile
export function getActiveUser(config: AppConfig): UserProfile {
  return config.users[config.activeUser] || { username: config.activeUser, enabledGames: {} };
}

// Convenience: get enabled games for the active user
export function getEnabledGames(config: AppConfig): Record<string, GameState> {
  return getActiveUser(config).enabledGames;
}

const STORE_KEY = "config";
const DEFAULT_CONFIG: AppConfig = {
  serverUrl: "",
  apiKey: "",
  wizardCompleted: false,
  activeUser: "",
  users: {},
};

let _store: any = null;
let _config: AppConfig = { ...DEFAULT_CONFIG };

async function getStore() {
  if (_store) return _store;
  try {
    const { load } = await import("@tauri-apps/plugin-store");
    _store = await load("config.json", { autoSave: true } as any);
    return _store;
  } catch {
    return null;
  }
}

export async function loadConfig(): Promise<AppConfig> {
  const store = await getStore();
  if (store) {
    const saved = await store.get(STORE_KEY);
    if (saved) {
      _config = migrateConfig({ ...DEFAULT_CONFIG, ...saved });
      return _config;
    }
  } else {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved) {
      try {
        _config = migrateConfig({ ...DEFAULT_CONFIG, ...JSON.parse(saved) });
        return _config;
      } catch {}
    }
  }
  return { ...DEFAULT_CONFIG };
}

/** Migrate old single-user config to multi-user format */
function migrateConfig(config: any): AppConfig {
  // Old format had `username` + `enabledGames` at top level
  if (config.username && !config.users) {
    const username = config.username;
    config.activeUser = username;
    config.users = {
      [username]: {
        username,
        enabledGames: config.enabledGames || {},
      },
    };
    delete config.username;
    delete config.enabledGames;
  }
  // Ensure activeUser exists in users
  if (config.activeUser && !config.users[config.activeUser]) {
    config.users[config.activeUser] = { username: config.activeUser, enabledGames: {} };
  }
  return config as AppConfig;
}

export async function saveConfig(config: AppConfig): Promise<void> {
  _config = config;
  const store = await getStore();
  if (store) {
    await store.set(STORE_KEY, config);
  } else {
    localStorage.setItem(STORE_KEY, JSON.stringify(config));
  }
}

export function getConfig(): AppConfig {
  return _config;
}
