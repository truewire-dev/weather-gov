//! TRU-404: the regenerated walker and the private dispatch, driven the way a user would.
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use truewire_core::serde_json::{self, json, Value};
use truewire_core::{Error, HttpCall, HttpEndpoint, Result};
use weather_gov::meta::DefaultMeta;
use weather_gov::stations::get_observations::Request;
use weather_gov::{CallOptions, Weather};

/// The 76 recorded KSEA observations, answered like api.weather.gov: `start` inclusive,
/// `end` exclusive, newest first, at most `limit` rows, `limit > 500` refused.
struct Service {
    rows: Vec<Value>,
    sent: Mutex<Vec<Value>>,
}

fn at(ts: &str) -> &str {
    &ts[..19] // every recorded timestamp is UTC
}

#[async_trait]
impl HttpEndpoint<DefaultMeta> for Service {
    async fn request(&self, call: HttpCall<'_, DefaultMeta>) -> Result<Value> {
        let request = call.request.unwrap();
        self.sent.lock().unwrap().push(request.clone());
        let limit = request.get("limit").and_then(Value::as_i64).unwrap_or(500);
        if !(1..=500).contains(&limit) {
            return Err(Error::logic(format!("HTTP 400: query.limit {limit}")));
        }
        let start = request.get("start").and_then(Value::as_str).map(|s| at(s).to_owned());
        let end = request.get("end").and_then(Value::as_str).map(|s| at(s).to_owned());
        let rows: Vec<Value> = self
            .rows
            .iter()
            .filter(|row| {
                let ts = at(row["properties"]["timestamp"].as_str().unwrap());
                start.as_deref().is_none_or(|s| ts >= s) && end.as_deref().is_none_or(|e| ts < e)
            })
            .take(limit as usize)
            .cloned()
            .collect();
        Ok(json!({"type": "FeatureCollection", "features": rows}))
    }
}

fn service() -> Arc<Service> {
    let recorded: Value = serde_json::from_str(include_str!(
        "../../../spec/endpoints/stations/get_observations/examples/ksea_window.response.json"
    ))
    .unwrap();
    let rows = recorded["payload"]["features"].as_array().unwrap().clone();
    assert_eq!(rows.len(), 76);
    Arc::new(Service { rows, sent: Mutex::new(vec![]) })
}

struct Shared(Arc<Service>);

#[async_trait]
impl HttpEndpoint<DefaultMeta> for Shared {
    async fn request(&self, call: HttpCall<'_, DefaultMeta>) -> Result<Value> {
        self.0.request(call).await
    }
}

#[tokio::test]
async fn every_limit_walks_all_76_newest_first_and_sends_a_legal_limit() {
    for limit in [None, Some(i64::MIN), Some(-5), Some(0), Some(1), Some(2), Some(7), Some(10), Some(500), Some(1000), Some(i64::MAX)] {
        let service = service();
        let client = Weather::from_core(Shared(service.clone()));
        let request = Request { station_id: "KSEA".into(), limit, ..Default::default() };
        let rows = client.stations.get_observations_paged(request, CallOptions::default()).await.unwrap();
        let ts: Vec<String> = rows.iter().map(|row| format!("{:?}", row.properties.timestamp)).collect();
        let sent: Vec<Value> = service.sent.lock().unwrap().iter().map(|r| r.get("limit").cloned().unwrap_or(Value::Null)).collect();
        eprintln!("limit {limit:?}: {} rows in {} calls, first sent limit {}", rows.len(), sent.len(), sent[0]);
        assert_eq!(rows.len(), 76, "limit {limit:?}");
        assert!(ts.windows(2).all(|w| w[0] > w[1]), "limit {limit:?}: not strictly newest first");
    }
}

#[tokio::test]
async fn the_walk_stops_at_the_callers_start() {
    let service = service();
    let start = service.rows[50]["properties"]["timestamp"].clone();
    let client = Weather::from_core(Shared(service.clone()));
    let request = Request { station_id: "KSEA".into(), limit: Some(7), start: serde_json::from_value(start).unwrap(), ..Default::default() };
    let rows = client.stations.get_observations_paged(request, CallOptions::default()).await.unwrap();
    assert_eq!(rows.len(), 51);
}

#[tokio::test]
async fn call_is_reachable_but_a_paged_name_is_not() {
    let client = Weather::from_core(Shared(service()));
    let request = json!({"station_id": "KSEA", "limit": 3});
    let body = client.call("stations.get_observations", request.clone(), CallOptions::default()).await.unwrap();
    assert_eq!(body["features"].as_array().unwrap().len(), 3);
    let err = client.call("stations.get_observations_paged", request, CallOptions::default()).await.unwrap_err();
    eprintln!("call(\"stations.get_observations_paged\") -> {err}");
}
