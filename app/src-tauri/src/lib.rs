use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

const ENGINE_BASE_URL: &str = "http://127.0.0.1:8000";

/// Holds the spawned engine sidecar so it can be shut down when the app exits.
struct EngineProcess(Mutex<Option<CommandChild>>);

#[tauri::command]
async fn ping_engine() -> Result<String, String> {
  let client = reqwest::Client::builder()
    .timeout(std::time::Duration::from_secs(3))
    .build()
    .map_err(|e| e.to_string())?;

  let response = client
    .get(format!("{ENGINE_BASE_URL}/ping"))
    .send()
    .await
    .map_err(|e| format!("engine unreachable: {e}"))?;

  response
    .text()
    .await
    .map_err(|e| format!("failed to read engine response: {e}"))
}

async fn engine_healthy() -> bool {
  let client = match reqwest::Client::builder()
    .timeout(std::time::Duration::from_secs(2))
    .build()
  {
    Ok(client) => client,
    Err(_) => return false,
  };
  client
    .get(format!("{ENGINE_BASE_URL}/health"))
    .send()
    .await
    .map(|r| r.status().is_success())
    .unwrap_or(false)
}

/// Cadence's default per-user home: Music\Cadence. Music is never given a
/// virtualized private view by Windows (AppData can be), and it's where a
/// music app's files belong.
fn default_data_dir(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
  app.path().audio_dir().ok().map(|music| music.join("Cadence"))
}

/// The user's storage override lives at the DEFAULT location even when data
/// is stored elsewhere, so it can always be found again.
fn config_path(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
  default_data_dir(app).map(|d| d.join("config.json"))
}

fn read_data_dir_override(app: &tauri::AppHandle) -> Option<String> {
  let path = config_path(app)?;
  let text = std::fs::read_to_string(path).ok()?;
  let cfg: serde_json::Value = serde_json::from_str(&text).ok()?;
  let dir = cfg.get("data_dir")?.as_str()?.trim();
  if dir.is_empty() { None } else { Some(dir.to_string()) }
}

/// Where the engine keeps everything (models, tracks, database) right now.
#[tauri::command]
fn get_data_dir(app: tauri::AppHandle) -> serde_json::Value {
  let default = default_data_dir(&app)
    .map(|d| d.to_string_lossy().to_string())
    .unwrap_or_default();
  let overridden = read_data_dir_override(&app);
  serde_json::json!({
    "default": default,
    "override": overridden,
    "effective": overridden.clone().unwrap_or(default),
  })
}

/// Point Cadence at a different storage folder (empty clears the override).
/// Takes effect when the engine restarts.
#[tauri::command]
fn set_data_dir(app: tauri::AppHandle, path: String) -> Result<(), String> {
  let cfg_path = config_path(&app).ok_or("no Music folder available")?;
  let trimmed = path.trim();
  if !trimmed.is_empty() {
    let dir = std::path::Path::new(trimmed);
    if !dir.is_absolute() {
      return Err("Use a full path, like D:\\CadenceData".into());
    }
    std::fs::create_dir_all(dir).map_err(|e| format!("Can't create that folder: {e}"))?;
    let probe = dir.join(".cadence-write-test");
    std::fs::write(&probe, "ok").map_err(|e| format!("Can't write there: {e}"))?;
    let _ = std::fs::remove_file(&probe);
  }
  if let Some(parent) = cfg_path.parent() {
    std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
  }
  let cfg = serde_json::json!({ "data_dir": trimmed });
  std::fs::write(&cfg_path, serde_json::to_string_pretty(&cfg).unwrap())
    .map_err(|e| format!("Couldn't save the setting: {e}"))
}

/// Stop the engine sidecar and start a fresh one (picks up a new data dir).
#[tauri::command]
fn restart_engine(app: tauri::AppHandle) {
  if let Some(child) = app.state::<EngineProcess>().0.lock().unwrap().take() {
    stop_engine(child);
  }
  start_engine(app);
}

/// Open a URL or local folder with the OS default handler, no console flash.
fn open_external(target: &str) {
  #[cfg(windows)]
  {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = std::process::Command::new("cmd")
      .args(["/C", "start", "", target])
      .creation_flags(CREATE_NO_WINDOW)
      .spawn();
  }
  #[cfg(target_os = "macos")]
  {
    let _ = std::process::Command::new("open").arg(target).spawn();
  }
  #[cfg(all(unix, not(target_os = "macos")))]
  {
    let _ = std::process::Command::new("xdg-open").arg(target).spawn();
  }
}

/// Open the GitHub releases page in the default browser so the user can
/// download a newer installer. Fixed URL — nothing from the webview is run.
#[tauri::command]
fn open_releases_page() {
  open_external("https://github.com/JoeMighty/Cadence/releases");
}

/// Open a local folder (e.g. the error log directory) in the file manager.
/// Validated to an existing directory, so only a folder is ever opened.
#[tauri::command]
fn open_folder(path: String) -> Result<(), String> {
  if !std::path::Path::new(&path).is_dir() {
    return Err(format!("Not a folder: {path}"));
  }
  open_external(&path);
  Ok(())
}

/// Start the bundled engine sidecar, unless an engine is already running
/// (e.g. one started by hand during development).
fn start_engine(app: tauri::AppHandle) {
  tauri::async_runtime::spawn(async move {
    if engine_healthy().await {
      log::info!("engine already reachable; not starting the sidecar");
      return;
    }
    let command = match app.shell().sidecar("cadence-engine") {
      Ok(command) => command,
      Err(err) => {
        log::error!("engine sidecar not available: {err}");
        return;
      }
    };
    // Windows can hand a spawned sidecar a virtualized, private view of AppData:
    // files the user installed there look missing, and files the engine writes
    // never reach the real profile. Music is never virtualized — and it's where
    // a music app's data belongs — so Cadence lives in Music\Cadence unless the
    // user pointed it elsewhere in Settings. Keep the default in sync with the
    // engine and scripts/setup-backends.
    let mut command = command.env("CADENCE_PORT", "8000");
    let data_dir = read_data_dir_override(&app)
      .map(std::path::PathBuf::from)
      .or_else(|| default_data_dir(&app));
    if let Some(dir) = data_dir {
      command = command.env("CADENCE_DATA_DIR", dir.to_string_lossy().to_string());
    }
    match command.spawn() {
      Ok((mut rx, child)) => {
        app.state::<EngineProcess>().0.lock().unwrap().replace(child);
        log::info!("engine sidecar started");
        while rx.recv().await.is_some() {}
      }
      Err(err) => log::error!("failed to start engine sidecar: {err}"),
    }
  });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .manage(EngineProcess(Mutex::new(None)))
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      start_engine(app.handle().clone());
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      ping_engine,
      open_releases_page,
      open_folder,
      get_data_dir,
      set_data_dir,
      restart_engine
    ])
    .build(tauri::generate_context!())
    .expect("error while running tauri application")
    .run(|app_handle, event| {
      if let RunEvent::ExitRequested { .. } = event {
        if let Some(child) = app_handle.state::<EngineProcess>().0.lock().unwrap().take() {
          stop_engine(child);
        }
      }
    });
}

/// Kill the engine sidecar and its whole tree. PyInstaller's onefile build
/// runs a bootloader that re-launches the real Python process, so killing the
/// tracked child alone leaves that grandchild orphaned — hence `taskkill /T`.
fn stop_engine(child: CommandChild) {
  #[cfg(windows)]
  {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = std::process::Command::new("taskkill")
      .args(["/PID", &child.pid().to_string(), "/T", "/F"])
      .creation_flags(CREATE_NO_WINDOW)
      .status();
  }
  #[cfg(unix)]
  {
    // Same story on macOS/Linux: the onefile bootloader forks the real Python
    // process. Kill the bootloader's children first, then the bootloader.
    let pid = child.pid().to_string();
    let _ = std::process::Command::new("pkill").args(["-9", "-P", &pid]).status();
    let _ = std::process::Command::new("kill").args(["-9", &pid]).status();
  }
  let _ = child.kill();
}
