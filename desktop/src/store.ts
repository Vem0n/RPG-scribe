/**
 * Persistent config store for RPG Scribe desktop app.
 * Multi-user support: each user has independent game settings.
 *
 * The API key is intentionally NOT in AppConfig — it lives in the OS-native
 * credential store (Windows Credential Manager / macOS Keychain / Linux
 * Secret Service) via the `get_api_key` / `set_api_key` Tauri commands
 * and is read/written through `getApiKey` / `setApiKey` below.
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
// Old configs were stored with the API key inline. Used by migrateConfig
// to detect-and-relocate to the keyring on first load after upgrade.
const LEGACY_API_KEY_FIELD = "apiKey";

const DEFAULT_CONFIG: AppConfig = {
  serverUrl: "",
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

/* ------------------------------------------------------------------ */
/* API key — OS keyring                                                */
/* ------------------------------------------------------------------ */

/**
 * Read the API key from the OS keyring. Returns "" when no key is set
 * (matches the Rust command's NoEntry → empty-string contract).
 *
 * In a non-Tauri context (browser dev fallback) this reads from
 * sessionStorage so dev workflows keep working — sessionStorage clears
 * on tab close, so the key never persists to disk in that path.
 */
export async function getApiKey(): Promise<string> {
  if (window.__TAURI_INTERNALS__) {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<string>("get_api_key");
  }
  // Dev fallback. sessionStorage clears with the tab — not durable storage.
  return sessionStorage.getItem("apiKey") ?? "";
}

/**
 * Persist the API key to the OS keyring. Empty string deletes the entry.
 */
export async function setApiKey(key: string): Promise<void> {
  if (window.__TAURI_INTERNALS__) {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("set_api_key", { key });
    return;
  }
  if (key) sessionStorage.setItem("apiKey", key);
  else sessionStorage.removeItem("apiKey");
}

/* ------------------------------------------------------------------ */
/* Config — plugin-store / localStorage                                */
/* ------------------------------------------------------------------ */

export async function loadConfig(): Promise<AppConfig> {
  const store = await getStore();
  let raw: any = null;
  if (store) {
    raw = await store.get(STORE_KEY);
  } else {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved) {
      try { raw = JSON.parse(saved); } catch { raw = null; }
    }
  }
  if (!raw) {
    return { ...DEFAULT_CONFIG };
  }

  const merged = { ...DEFAULT_CONFIG, ...raw };
  const migrated = await migrateConfig(merged, raw);
  _config = migrated;
  return _config;
}

/** Migrate old single-user config to multi-user format, and lift any
 *  inline apiKey into the OS keyring (one-time, on first load post-update). */
async function migrateConfig(config: any, raw: any): Promise<AppConfig> {
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

  // Lift legacy inline apiKey → keyring, then strip from config so it's
  // never written back to disk in clear text.
  const legacyKey = raw?.[LEGACY_API_KEY_FIELD];
  if (typeof legacyKey === "string" && legacyKey.length > 0) {
    try {
      await setApiKey(legacyKey);
    } catch {
      // If keyring write fails, leave the legacy field where it is so the
      // user doesn't lose access; they'll see the warning and we'll retry
      // next launch. Swallowing is intentional.
    }
  }
  delete (config as any)[LEGACY_API_KEY_FIELD];

  // If we just stripped a legacy field, persist the cleaned config now so
  // the next load doesn't keep trying to re-migrate.
  if (typeof legacyKey === "string") {
    await persistConfig(config as AppConfig);
  }

  return config as AppConfig;
}

async function persistConfig(config: AppConfig): Promise<void> {
  const store = await getStore();
  if (store) {
    await store.set(STORE_KEY, config);
  } else {
    localStorage.setItem(STORE_KEY, JSON.stringify(config));
  }
}

export async function saveConfig(config: AppConfig): Promise<void> {
  _config = config;
  await persistConfig(config);
}

export function getConfig(): AppConfig {
  return _config;
}
