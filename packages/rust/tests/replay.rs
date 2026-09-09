//! Every recorded example replayed through the generated Rust client against `truewire
//! mock`, which serves the same recordings over real HTTP. Nothing here touches the
//! network.
//!
//! The assertions are the Rust half of `packages/python/test/test_recordings.py` and
//! `packages/typescript/test/replay.test.ts`: structural, not literal, because the counts
//! and the text move with every re-recording and the shape does not. Where the other two
//! prove a thing about a response, this proves the same thing about the same response, so
//! a divergence between the three clients is a test failure rather than a discovery
//! months later.

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

use truewire_core::serde_json::Value;
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::types::QuantitativeValue;
use weather_gov::Weather;

const CONTACT: &str = "tests@truewire.dev";

/// The repository root, three levels above this package.
fn project_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .expect("packages/rust sits two levels below the repository root")
        .to_path_buf()
}

/// `truewire mock`, on a free port, with the URL it printed.
struct Mock {
    child: Child,
    http: String,
}

impl Drop for Mock {
    fn drop(&mut self) {
        let _ = self.child.kill();
    }
}

fn start_mock() -> Mock {
    let root = project_root();
    let bin = std::env::var("TRUEWIRE_BIN")
        .map(PathBuf::from)
        .unwrap_or_else(|_| root.join(".venv/bin/truewire"));
    let mut child = Command::new(&bin)
        .args(["mock", "--project"])
        .arg(&root)
        .args(["--http-port", "0", "--ws-port", "0"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap_or_else(|e| panic!("could not start {}: {e}", bin.display()));
    let stdout = child.stdout.take().expect("piped");
    let mut lines = BufReader::new(stdout).lines();
    let mut http = None;
    for line in lines.by_ref() {
        let line = line.expect("mock stdout");
        let mut parts = line.split_whitespace();
        if let (Some("HTTP"), Some(url)) = (parts.next(), parts.next()) {
            http = Some(url.to_string());
            break;
        }
    }
    // Keep draining. The mock writes to stdout for the life of the process, and a pipe
    // nobody reads fills up: it then blocks on the write, or takes EPIPE if the reader has
    // gone, and dies mid-response. That showed up here as `IncompleteBody` and
    // `ConnectionReset` on three of eight tests -- a real bug in the harness reading as
    // flakiness in the client.
    std::thread::spawn(move || lines.for_each(drop));
    Mock { child, http: http.expect("the mock printed an HTTP url") }
}

fn client(mock: &Mock) -> Weather {
    Weather::with_options(CoreOptions::new(CONTACT).base_url(mock.http.clone()))
}

/// The request half of one recorded example: the source of truth for what to replay.
///
/// Read rather than written here, because `refresh_examples.py` moves the observation
/// window and the alert identifier before every re-recording -- a constant would turn that
/// repair into a test failure.
fn recorded(file: &str) -> Value {
    let path = project_root().join("spec/endpoints").join(file);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("could not read {}: {e}", path.display()));
    let value: Value = truewire_core::serde_json::from_str(&text).expect("valid json");
    value["request"].clone()
}

/// A recorded ISO timestamp, read through the type's own `Deserialize`.
fn timestamp(value: &Value) -> truewire_core::types::TimestampIso {
    truewire_core::serde_json::from_value(value.clone()).expect("an RFC 3339 timestamp")
}

/// A `QuantitativeValue`: a unit, and a number or an honest null.
fn is_measurement(value: &QuantitativeValue, unit: Option<&str>) {
    assert!(
        value.unit_code.starts_with("wmoUnit:"),
        "{}",
        value.unit_code
    );
    if let Some(unit) = unit {
        assert_eq!(value.unit_code, unit);
    }
}

#[tokio::test]
async fn points_get_point_returns_the_payload_not_the_wrapper() {
    let mock = start_mock();
    let client = client(&mock);
    let point = client
        .points
        .get_point(
            weather_gov::points::get_point::Request {
                latitude: 47.6062,
                longitude: -122.3321,
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_point");
    // The declared envelope, working: this is `properties`, not the GeoJSON feature.
    assert_eq!(point.grid_id, "SEW");
    assert_eq!(point.grid_x, 125);
    assert_eq!(point.grid_y, 68);
    assert_eq!(point.time_zone, "America/Los_Angeles");
    let nearest = point
        .relative_location
        .as_ref()
        .expect("a nearest city")
        .properties
        .clone();
    assert_eq!(nearest.city, "Seattle");
    assert_eq!(nearest.state, "WA");
}

#[tokio::test]
async fn forecast_get_forecast_returns_fourteen_periods() {
    let mock = start_mock();
    let client = client(&mock);
    let forecast = client
        .forecast
        .get_forecast(
            weather_gov::forecast::get_forecast::Request {
                office: "SEW".to_string(),
                grid_x: 125,
                grid_y: 68,
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_forecast");
    assert_eq!(forecast.periods.len(), 14);
    for (index, period) in forecast.periods.iter().enumerate() {
        assert_eq!(period.number, index as i64 + 1);
        // The one place this API sends a bare number beside a unit *string*.
        assert!(!period.short_forecast.is_empty());
        is_measurement(
            period
                .probability_of_precipitation
                .as_ref()
                .expect("a chance of precipitation"),
            Some("wmoUnit:percent"),
        );
    }
}

#[tokio::test]
async fn stations_list_stations_sends_a_repeated_query_key() {
    let mock = start_mock();
    let client = client(&mock);
    // `state: ["WA"]` has to reach the wire as `?state=WA`, not as one JSON string. The
    // mock matches the recorded query exactly, so a wrong rendering fails here.
    let page = client
        .stations
        .list_stations(
            weather_gov::stations::list_stations::Request {
                state: Some(vec!["WA".to_string()]),
                limit: Some(20),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_stations");
    assert_eq!(page.features.len(), 20);
    for feature in &page.features {
        assert!(!feature.properties.station_identifier.is_empty());
    }
}

#[tokio::test]
async fn stations_get_latest_observation_carries_a_unit_on_every_measurement() {
    let mock = start_mock();
    let client = client(&mock);
    let now = client
        .stations
        .get_latest_observation(
            weather_gov::stations::get_latest_observation::Request {
                station_id: "KSEA".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_latest_observation");
    is_measurement(&now.temperature, Some("wmoUnit:degC"));
    is_measurement(&now.dewpoint, Some("wmoUnit:degC"));
    is_measurement(&now.wind_speed, Some("wmoUnit:km_h-1"));
    for layer in &now.cloud_layers {
        is_measurement(&layer.base, Some("wmoUnit:m"));
    }
}

#[tokio::test]
async fn stations_get_observations_answers_newest_first() {
    let mock = start_mock();
    let client = client(&mock);
    let window = recorded("stations/get_observations/examples/ksea_window.request.json");
    let page = client
        .stations
        .get_observations(
            weather_gov::stations::get_observations::Request {
                station_id: window["station_id"].as_str().expect("a station").to_string(),
                // Through the field's own `Deserialize`, which is the same code path the
                // client uses on the wire -- so the test cannot parse a timestamp in a way
                // the client would not.
                start: Some(timestamp(&window["start"])),
                end: Some(timestamp(&window["end"])),
                limit: window["limit"].as_i64(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_observations");
    assert!(!page.features.is_empty());
    // Under the service's cap, which is what makes this the example that walks rather than
    // the one that shows truncation.
    assert!(page.features.len() < 500);
    let timestamps: Vec<_> = page
        .features
        .iter()
        .map(|feature| feature.properties.timestamp)
        .collect();
    let mut sorted = timestamps.clone();
    sorted.sort();
    sorted.reverse();
    assert_eq!(timestamps, sorted, "the service answers newest first");
}

#[tokio::test]
async fn alerts_honour_filters_that_disagree_about_capitalisation() {
    let mock = start_mock();
    let client = client(&mock);
    let page = client
        .alerts
        .get_active_alerts(
            weather_gov::alerts::get_active_alerts::Request {
                status: Some(vec![
                    weather_gov::alerts::get_active_alerts::RequestStatusItem::Actual,
                ]),
                severity: Some(vec![
                    weather_gov::alerts::get_active_alerts::RequestSeverityItem::Severe,
                ]),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_active_alerts");
    assert!(!page.features.is_empty());
    for feature in &page.features {
        assert!(feature.properties.id.starts_with("urn:oid:"));
        assert!(!feature.properties.event.is_empty());
    }
}

#[tokio::test]
async fn alerts_get_alert_keeps_the_whole_feature_and_a_colon_in_the_path() {
    let mock = start_mock();
    let client = client(&mock);
    let recorded = recorded("alerts/get_alert/examples/one.request.json");
    let id = recorded["id"].as_str().expect("an alert id").to_string();
    // The identifier is `urn:oid:...`, so this also proves `:` survived the path unencoded.
    assert!(id.contains(':'));
    let alert = client
        .alerts
        .get_alert(
            weather_gov::alerts::get_alert::Request { id: id.clone(), ..Default::default() },
            CallOptions::default(),
        )
        .await
        .expect("get_alert");
    assert_eq!(alert.properties.id, id);
}

#[tokio::test]
async fn offices_and_products_answer_in_their_own_vocabularies() {
    let mock = start_mock();
    let client = client(&mock);
    let office = client
        .offices
        .get_office(
            weather_gov::offices::get_office::Request {
                office_id: "SEW".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_office");
    // schema.org, not GeoJSON.
    assert_eq!(office.id, "SEW");

    let types = client
        .products
        .list_product_types(
            weather_gov::products::list_product_types::Request::default(),
            CallOptions::default(),
        )
        .await
        .expect("list_product_types");
    // JSON-LD, a third vocabulary from the same host.
    assert!(types.graph.len() > 300);
    assert!(types.graph.iter().any(|entry| entry.product_code == "AFD"));
}
