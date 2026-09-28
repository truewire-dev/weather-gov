use truewire_core::{serde_json::json, CallOptions};
use weather_gov::core::CoreOptions;
use weather_gov::Weather;

#[tokio::main]
async fn main() {
    let client = Weather::with_options(CoreOptions::new("r@r").base_url("http://127.0.0.1:8765".to_string()));
    let ok = client.call("stations.get_observations", json!({"station_id": "KSEA", "limit": 3}), CallOptions::default()).await;
    println!("ok: {}", ok.map(|v| v["features"].as_array().unwrap().len().to_string()).unwrap_or_else(|e| e.to_string()));
    let typo = client.call("stations.get_observation", json!({"station_id": "KSEA"}), CallOptions::default()).await;
    println!("typo: {}", typo.unwrap_err());
    let bad = client.call("stations.get_observations", json!({"station": "KSEA"}), CallOptions::default()).await;
    println!("bad request: {}", bad.unwrap_err());
    let paged = client.call("stations.get_observations_paged", json!({"station_id": "KSEA"}), CallOptions::default()).await;
    println!("paged: {}", paged.map(|_| "ok".to_string()).unwrap_or_else(|e| e.to_string()));
}
