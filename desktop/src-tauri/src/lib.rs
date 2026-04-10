use notify_debouncer_mini::{new_debouncer, DebouncedEventKind};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager,
};

mod watcher;

/// Shared app state
pub struct AppState {
    pub watchers: Mutex<HashMap<String, watcher::WatcherHandle>>,
}

/// Start watching a directory for save file changes.
/// Called from the frontend when a game is enabled.
#[tauri::command]
fn start_watching(
    app: tauri::AppHandle,
    state: tauri::State<AppState>,
    game_id: String,
    save_path: String,
    playthrough: Option<String>,
) -> Result<(), String> {
    let mut watchers = state.watchers.lock().map_err(|e| e.to_string())?;

    // Stop existing watcher for this game
    watchers.remove(&game_id);

    let watch_path = if let Some(ref pt) = playthrough {
        PathBuf::from(&save_path).join(pt)
    } else {
        PathBuf::from(&save_path)
    };

    if !watch_path.exists() {
        return Err(format!("Path does not exist: {}", watch_path.display()));
    }

    let handle = watcher::start_watcher(app, game_id.clone(), watch_path)
        .map_err(|e| format!("Failed to start watcher: {}", e))?;

    watchers.insert(game_id, handle);
    Ok(())
}

/// Stop watching a game's save directory.
#[tauri::command]
fn stop_watching(state: tauri::State<AppState>, game_id: String) -> Result<(), String> {
    let mut watchers = state.watchers.lock().map_err(|e| e.to_string())?;
    watchers.remove(&game_id);
    Ok(())
}

/// Run a scraper script synchronously and return the output.
#[tauri::command]
async fn run_scraper(
    script_path: String,
    save_path: String,
    server_url: String,
    username: String,
    api_key: String,
) -> Result<String, String> {
    // Resolve script path relative to project root (two levels up from src-tauri)
    let project_root = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();

    // In dev, CWD is desktop/src-tauri; in production, use exe dir
    // Try multiple base paths to find the script
    let candidates = [
        PathBuf::from(&script_path),
        std::env::current_dir().unwrap_or_default().join(&script_path),
        std::env::current_dir().unwrap_or_default().join("..").join(&script_path),
        std::env::current_dir().unwrap_or_default().join("../..").join(&script_path),
        project_root.join(&script_path),
        project_root.join("..").join(&script_path),
    ];

    let resolved = candidates.iter()
        .find(|p| p.exists())
        .cloned()
        .unwrap_or_else(|| PathBuf::from(&script_path));

    log::info!("Running scraper: python {} {}", resolved.display(), save_path);

    let output = tokio::process::Command::new("python")
        .arg(resolved.as_os_str())
        .arg(&save_path)
        .arg("--server")
        .arg(&server_url)
        .arg("--username")
        .arg(&username)
        .arg("--api-key")
        .arg(&api_key)
        .output()
        .await
        .map_err(|e| format!("Failed to run scraper: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(stdout)
    } else {
        Err(format!("Scraper failed:\n{}\n{}", stdout, stderr))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            watchers: Mutex::new(HashMap::new()),
        })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // System tray
            let show = MenuItem::with_id(app, "show", "Show RPG Scribe", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;

            TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("RPG Scribe — Watching for saves")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            // Minimize to tray on close
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .invoke_handler(tauri::generate_handler![
            start_watching,
            stop_watching,
            run_scraper,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
