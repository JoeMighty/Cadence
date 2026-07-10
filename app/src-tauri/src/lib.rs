const ENGINE_BASE_URL: &str = "http://127.0.0.1:8000";

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![ping_engine])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
