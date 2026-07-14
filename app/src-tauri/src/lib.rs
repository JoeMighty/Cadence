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

/// Open the GitHub releases page in the default browser so the user can
/// download a newer installer. Fixed URL — nothing from the webview is run.
#[tauri::command]
fn open_releases_page() {
  #[cfg(windows)]
  {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = std::process::Command::new("cmd")
      .args(["/C", "start", "", "https://github.com/JoeMighty/Cadence/releases"])
      .creation_flags(CREATE_NO_WINDOW)
      .spawn();
  }
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
    // The frozen engine chooses its own per-user data dir (%LOCALAPPDATA%\Cadence)
    // — the same place scripts/setup-backends installs the AI models — so we
    // deliberately don't override CADENCE_DATA_DIR here.
    let command = command.env("CADENCE_PORT", "8000");
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
    .invoke_handler(tauri::generate_handler![ping_engine, open_releases_page])
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
  let _ = child.kill();
}
