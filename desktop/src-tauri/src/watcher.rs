use notify_debouncer_mini::{new_debouncer, DebouncedEventKind};
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::{Duration, Instant};
use tauri::Emitter;

/// Handle to a running file watcher. Dropping it stops the watcher.
pub struct WatcherHandle {
    _debouncer: notify_debouncer_mini::Debouncer<notify::RecommendedWatcher>,
    _thread: std::thread::JoinHandle<()>,
}

/// Event emitted to the frontend when a save file changes.
#[derive(Clone, serde::Serialize)]
pub struct SaveChangeEvent {
    pub game_id: String,
    pub path: String,
}

/// Start watching a directory for file changes.
/// Uses a 5-second debounce from the notify crate PLUS
/// a 10-second cooldown after emitting an event to prevent
/// duplicate syncs from multi-file saves.
pub fn start_watcher(
    app: tauri::AppHandle,
    game_id: String,
    watch_path: PathBuf,
) -> Result<WatcherHandle, Box<dyn std::error::Error>> {
    let (tx, rx) = mpsc::channel();

    let mut debouncer = new_debouncer(Duration::from_secs(5), tx)
        .map_err(|e| -> Box<dyn std::error::Error> { Box::new(e) })?;

    debouncer.watcher().watch(
        &watch_path,
        notify::RecursiveMode::Recursive,
    )?;

    let gid = game_id.clone();
    let wp = watch_path.clone();
    let thread = std::thread::spawn(move || {
        log::info!("Watcher started for {} at {}", gid, wp.display());
        let mut last_emit = Instant::now() - Duration::from_secs(60); // Allow immediate first emit
        let cooldown = Duration::from_secs(10);

        loop {
            match rx.recv() {
                Ok(Ok(events)) => {
                    let has_change = events
                        .iter()
                        .any(|e| matches!(e.kind, DebouncedEventKind::Any));

                    if !has_change {
                        continue;
                    }

                    // Cooldown: skip if we emitted recently
                    if last_emit.elapsed() < cooldown {
                        log::info!("Skipping duplicate event for {} (cooldown)", gid);
                        continue;
                    }

                    // Find the most recently modified file
                    let latest = events
                        .iter()
                        .filter_map(|e| e.path.to_str().map(String::from))
                        .max_by_key(|p| {
                            std::fs::metadata(p)
                                .and_then(|m| m.modified())
                                .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                        });

                    if let Some(path) = latest {
                        log::info!("Save change detected for {}: {}", gid, path);
                        last_emit = Instant::now();
                        let _ = app.emit(
                            "save-changed",
                            SaveChangeEvent {
                                game_id: gid.clone(),
                                path,
                            },
                        );
                    }
                }
                Ok(Err(errors)) => {
                    log::warn!("Watcher errors for {}: {:?}", gid, errors);
                }
                Err(_) => {
                    log::info!("Watcher channel closed for {}", gid);
                    break;
                }
            }
        }
    });

    Ok(WatcherHandle {
        _debouncer: debouncer,
        _thread: thread,
    })
}
