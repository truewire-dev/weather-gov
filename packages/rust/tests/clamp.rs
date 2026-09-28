//! TRU-96: a caller asking for more than the service's 500-row cap still walks every page.
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use truewire_core::serde_json::{json, Value};
use truewire_core::{HttpCall, HttpEndpoint, Result};
use weather_gov::meta::DefaultMeta;
use weather_gov::stations::get_observations::{GetObservations, Request};
use weather_gov::CallOptions;

/// Answers like api.weather.gov: never more than 500 rows, whatever `limit` says.
struct CappedService {
    rows: Vec<Value>,
    sent: Mutex<Vec<(Option<Value>, Option<Value>)>>,
}

#[async_trait]
impl HttpEndpoint<DefaultMeta> for CappedService {
    async fn request(&self, call: HttpCall<'_, DefaultMeta>) -> Result<Value> {
        let request = call.request.unwrap();
        let mut sent = self.sent.lock().unwrap();
        let page = sent.len();
        sent.push((request.get("limit").cloned(), request.get("end").cloned()));
        let rows: Vec<Value> = self.rows.iter().skip(page * 500).take(500).cloned().collect();
        Ok(json!({"type": "FeatureCollection", "features": rows}))
    }
}

fn rows(n: usize) -> Vec<Value> {
    let recorded: Value = truewire_core::serde_json::from_str(include_str!(
        "../../../spec/endpoints/stations/get_observations/examples/ksea_window.response.json"
    ))
    .unwrap();
    let template = recorded["payload"]["features"][0].clone();
    (0..n)
        .map(|i| {
            let minutes = 23 * 60 + 59 - i;
            let ts = format!("2026-09-09T{:02}:{:02}:00+00:00", minutes / 60, minutes % 60);
            let mut row = template.clone();
            row["id"] = json!(format!("https://api.weather.gov/stations/KSEA/observations/{ts}"));
            row["properties"]["timestamp"] = json!(ts);
            row
        })
        .collect()
}

#[tokio::test]
async fn a_limit_over_the_cap_walks_past_the_first_full_page() {
    let service = Arc::new(CappedService { rows: rows(510), sent: Mutex::new(vec![]) });
    let endpoint = GetObservations::new(service.clone());
    let request = Request { station_id: "KSEA".into(), limit: Some(1000), ..Default::default() };
    let all = endpoint.get_observations_paged(request, CallOptions::default()).await.unwrap();
    let sent = service.sent.lock().unwrap().clone();
    eprintln!("rows = {}, calls = {:?}", all.len(), sent);
    assert_eq!(all.len(), 510);
}

/// api.weather.gov answers `limit=1000` with HTTP 400 ("Must have a maximum value of 500"),
/// so the size the walk measures pages against is also the one it must send.
#[tokio::test]
async fn the_walker_never_sends_a_limit_over_the_cap() {
    let service = Arc::new(CappedService { rows: rows(510), sent: Mutex::new(vec![]) });
    let endpoint = GetObservations::new(service.clone());
    let request = Request { station_id: "KSEA".into(), limit: Some(1000), ..Default::default() };
    endpoint.get_observations_paged(request, CallOptions::default()).await.unwrap();
    let limits: Vec<_> = service.sent.lock().unwrap().iter().map(|(limit, _)| limit.clone()).collect();
    assert!(limits.iter().all(|limit| limit.as_ref().and_then(Value::as_i64).is_some_and(|l| l <= 500)), "sent {limits:?}");
}
