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
    Mock {
        child,
        http: http.expect("the mock printed an HTTP url"),
    }
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

/// The response half of another recorded example, as it came off the wire.
fn payload(file: &str) -> Value {
    let path = project_root().join("spec/endpoints").join(file);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("could not read {}: {e}", path.display()));
    let value: Value = truewire_core::serde_json::from_str(&text).expect("valid json");
    value["payload"].clone()
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
                station_id: window["station_id"]
                    .as_str()
                    .expect("a station")
                    .to_string(),
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
            weather_gov::alerts::get_alert::Request {
                id: id.clone(),
                ..Default::default()
            },
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

/// A zone feature: its URL is its code, and a list leaves the outline out.
fn is_zone(feature: &weather_gov::types::ZoneFeature, geometry: bool) -> &weather_gov::types::Zone {
    let zone = &feature.properties;
    // `@id` renders as `id` and the zone code as `id2`: generator naming, not the wire's.
    assert_eq!(feature.id, zone.id);
    assert!(zone.id.ends_with(&format!("/{}", zone.id2)), "{}", zone.id);
    assert!(!zone.name.is_empty());
    assert!(zone.effective_date < zone.expiration_date);
    assert_eq!(feature.geometry.is_some(), geometry);
    zone
}

#[tokio::test]
async fn zones_list_zones_finds_one_zone_of_each_land_kind_at_a_point() {
    use weather_gov::types::ZoneType2;
    let mock = start_mock();
    let client = client(&mock);
    let page = client
        .zones
        .list_zones(
            weather_gov::zones::list_zones::Request {
                point: Some("47.6062,-122.3321".to_string()),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_zones");
    let zones: Vec<_> = page.features.iter().map(|f| is_zone(f, false)).collect();
    let mut kinds: Vec<_> = zones.iter().map(|zone| zone.type_2).collect();
    kinds.sort_by_key(|kind| format!("{kind:?}"));
    assert_eq!(
        kinds,
        [ZoneType2::County, ZoneType2::Fire, ZoneType2::Public]
    );
    assert!(zones.iter().any(|zone| zone.id2 == "WAZ315"));
    assert!(zones.iter().any(|zone| zone.id2 == "WAC033"));
}

#[tokio::test]
async fn zones_list_zones_honours_area_type_and_limit() {
    use weather_gov::types::ZoneKind;
    let mock = start_mock();
    let client = client(&mock);
    let page = client
        .zones
        .list_zones(
            weather_gov::zones::list_zones::Request {
                area: Some(vec!["WA".to_string()]),
                type_: Some(vec![ZoneKind::Fire]),
                limit: Some(3),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_zones");
    assert_eq!(page.features.len(), 3);
    let ids: Vec<_> = page
        .features
        .iter()
        .map(|f| {
            let zone = is_zone(f, false);
            assert_eq!(zone.type_2, weather_gov::types::ZoneType2::Fire);
            assert_eq!(zone.state, Some(Some("WA".to_string())));
            zone.id2.clone()
        })
        .collect();
    let mut sorted = ids.clone();
    sorted.sort();
    assert_eq!(ids, sorted, "the service orders zones by code");
}

#[tokio::test]
async fn zones_list_zones_by_type_takes_the_type_from_the_path() {
    use weather_gov::types::ZoneKind;
    let mock = start_mock();
    let client = client(&mock);
    let page = client
        .zones
        .list_zones_by_type(
            weather_gov::zones::list_zones_by_type::Request {
                // A request with a required enum has no `Default`, so every field is spelled.
                zone_type: ZoneKind::County,
                id: None,
                area: Some(vec!["WA".to_string()]),
                region: None,
                point: None,
                effective: None,
                limit: Some(5),
                extra: Default::default(),
            },
            CallOptions::default(),
        )
        .await
        .expect("list_zones_by_type");
    assert_eq!(page.features.len(), 5);
    for feature in &page.features {
        let zone = is_zone(feature, false);
        assert_eq!(zone.type_2, weather_gov::types::ZoneType2::County);
        assert!(zone.id2.starts_with("WAC"));
    }
}

#[tokio::test]
async fn zones_get_zone_keeps_the_outline_and_get_forecast_unwraps() {
    use weather_gov::types::ZoneKind;
    let mock = start_mock();
    let client = client(&mock);
    // One zone type for every endpoint that takes one.
    let kind = ZoneKind::Forecast;
    let feature = client
        .zones
        .get_zone(
            weather_gov::zones::get_zone::Request {
                zone_id: "WAZ315".to_string(),
                zone_type: kind,
                effective: None,
                extra: Default::default(),
            },
            CallOptions::default(),
        )
        .await
        .expect("get_zone");
    let zone = is_zone(&feature, true);
    assert_eq!(zone.id2, "WAZ315");
    assert_eq!(zone.name, "City of Seattle");
    assert_eq!(zone.grid_identifier.as_deref(), Some("SEW"));
    assert!(zone
        .observation_stations
        .as_ref()
        .expect("stations")
        .iter()
        .any(|url| url.ends_with("/stations/KSEA")));

    let forecast = client
        .zones
        .get_forecast(
            weather_gov::zones::get_forecast::Request {
                zone_id: "WAZ315".to_string(),
                zone_type: kind,
                extra: Default::default(),
            },
            CallOptions::default(),
        )
        .await
        .expect("get_forecast");
    // The declared envelope, working: the forecast, not the GeoJSON feature around it.
    assert!(forecast.zone.ends_with("/zones/forecast/WAZ315"));
    assert!(forecast.periods.len() > 6);
    for (index, period) in forecast.periods.iter().enumerate() {
        assert_eq!(period.number, index as i64 + 1);
        assert!(!period.name.is_empty() && !period.detailed_forecast.is_empty());
    }
}

#[tokio::test]
async fn zones_list_transmitters_answers_in_json_ld_for_the_county_asked() {
    let mock = start_mock();
    let client = client(&mock);
    let radio = client
        .zones
        .list_transmitters(
            // `zone_type` takes one value, `county`, so Rust fills it in and has no field.
            weather_gov::zones::list_transmitters::Request {
                zone_id: "WAC033".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_transmitters");
    assert!(!radio.graph.is_empty());
    for transmitter in &radio.graph {
        assert!(transmitter.counties.iter().any(|county| county == "WAC033"));
        // A decimal string on the wire, kept as one: 162.400 to 162.550 MHz.
        assert!(transmitter
            .transmitter_frequency
            .as_str()
            .starts_with("162."));
    }
    assert!(radio.graph.iter().any(|t| t.call_sign == "KHB60"));
}

#[tokio::test]
async fn stations_get_observations_for_zone_merges_stations_newest_first() {
    let mock = start_mock();
    let client = client(&mock);
    let window =
        recorded("stations/get_observations_for_zone/examples/seattle_capped.request.json");
    let start = timestamp(&window["start"]);
    let end = timestamp(&window["end"]);
    let limit = window["limit"].as_i64().expect("a limit");
    let page = client
        .stations
        .get_observations_for_zone(
            weather_gov::stations::get_observations_for_zone::Request {
                zone_id: window["zone_id"].as_str().expect("a zone").to_string(),
                start: Some(start),
                end: Some(end),
                limit: Some(limit),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_observations_for_zone");
    assert_eq!(page.features.len() as i64, limit);
    let timestamps: Vec<_> = page
        .features
        .iter()
        .map(|feature| feature.properties.timestamp)
        .collect();
    let mut sorted = timestamps.clone();
    sorted.sort();
    sorted.reverse();
    assert_eq!(timestamps, sorted, "the service answers newest first");
    assert!(timestamps
        .iter()
        .all(|stamp| start <= *stamp && *stamp < end));
    let mut unique = timestamps.clone();
    unique.dedup();
    // Timestamps repeat across stations: why this endpoint declares no seek walk.
    assert!(unique.len() < timestamps.len());
}

#[tokio::test]
async fn stations_for_a_zone_and_a_grid_cell() {
    let mock = start_mock();
    let client = client(&mock);
    let zone = client
        .stations
        .list_stations_for_zone(
            weather_gov::stations::list_stations_for_zone::Request {
                zone_id: "WAZ315".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_stations_for_zone");
    let urls: Vec<_> = zone.features.iter().map(|f| f.id.clone()).collect();
    assert_eq!(zone.observation_stations.as_ref(), Some(&urls));
    assert!(zone
        .features
        .iter()
        .any(|f| f.properties.station_identifier == "KSEA"));

    let grid = client
        .stations
        .list_stations_for_gridpoint(
            weather_gov::stations::list_stations_for_gridpoint::Request {
                office: "SEW".to_string(),
                grid_x: 125,
                grid_y: 68,
                limit: Some(5),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_stations_for_gridpoint");
    assert_eq!(grid.features.len(), 5);
    let mut distances = Vec::new();
    for feature in &grid.features {
        let distance = feature.properties.distance.as_ref().expect("a distance");
        is_measurement(distance, Some("wmoUnit:m"));
        let bearing = feature.properties.bearing.as_ref().expect("a bearing");
        is_measurement(bearing, Some("wmoUnit:degree_(angle)"));
        distances.push(distance.value.expect("a measured distance"));
    }
    assert!(
        distances.windows(2).all(|pair| pair[0] <= pair[1]),
        "nearest first"
    );
}

#[tokio::test]
async fn stations_get_station_keeps_the_whole_feature() {
    let mock = start_mock();
    let client = client(&mock);
    let station = client
        .stations
        .get_station(
            weather_gov::stations::get_station::Request {
                station_id: "KSEA".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_station");
    assert_eq!(station.id, "https://api.weather.gov/stations/KSEA");
    // The geometry is the only place the station's coordinates are.
    let (longitude, latitude) = station.geometry.as_ref().expect("a point").coordinates;
    assert_eq!((latitude.round(), longitude.round()), (47.0, -122.0));
    let properties = &station.properties;
    assert_eq!(properties.station_identifier, "KSEA");
    assert_eq!(properties.time_zone.as_deref(), Some("America/Los_Angeles"));
    is_measurement(
        properties.elevation.as_ref().expect("an elevation"),
        Some("wmoUnit:m"),
    );
    assert!(properties
        .county
        .as_deref()
        .expect("a county")
        .ends_with("/zones/county/WAC033"));
}

#[tokio::test]
async fn stations_get_observation_returns_the_observation_at_the_moment_asked() {
    let mock = start_mock();
    let client = client(&mock);
    let asked = recorded("stations/get_observation/examples/ksea_metar.request.json");
    let station = asked["station_id"].as_str().expect("a station").to_string();
    let observation = client
        .stations
        .get_observation(
            weather_gov::stations::get_observation::Request {
                station_id: station.clone(),
                time: timestamp(&asked["time"]),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_observation");
    assert_eq!(observation.station_id.as_deref(), Some(station.as_str()));
    assert_eq!(observation.timestamp, timestamp(&asked["time"]));
    assert!(observation
        .raw_message
        .as_deref()
        .expect("a METAR")
        .starts_with(&format!("{station} ")));
    is_measurement(&observation.temperature, Some("wmoUnit:degC"));
}

#[tokio::test]
async fn stations_list_tafs_answers_newest_first_with_a_latitude_first_point() {
    let mock = start_mock();
    let client = client(&mock);
    let tafs = client
        .stations
        .list_tafs(
            weather_gov::stations::list_tafs::Request {
                station_id: "KSEA".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_tafs");
    assert!(tafs.graph.len() > 10);
    let issued: Vec<_> = tafs.graph.iter().map(|taf| taf.issue_time).collect();
    let mut newest_first = issued.clone();
    newest_first.sort_by(|a, b| b.cmp(a));
    assert_eq!(issued, newest_first);
    for taf in &tafs.graph {
        assert_eq!(taf.location, "KSEA");
        assert!(taf
            .id
            .starts_with("https://api.weather.gov/stations/KSEA/tafs/"));
        assert!(taf.issue_time <= taf.start && taf.start < taf.end);
    }
    // Well-Known Text, latitude first: the reverse of the station's GeoJSON coordinates.
    let coordinates = payload("stations/get_station/examples/ksea.response.json")["geometry"]
        ["coordinates"]
        .clone();
    let longitude = coordinates[0].as_f64().expect("a longitude");
    let latitude = coordinates[1].as_f64().expect("a latitude");
    let point = tafs.graph[0].geometry.as_deref().expect("a point");
    let numbers: Vec<f64> = point
        .trim_start_matches("POINT(")
        .trim_end_matches(')')
        .split_whitespace()
        .map(|number| number.parse().expect("a number"))
        .collect();
    let hundredths = |value: f64| (value * 100.0).round() / 100.0;
    assert_eq!(numbers, vec![hundredths(latitude), hundredths(longitude)]);
}

#[tokio::test]
async fn offices_get_briefing_returns_an_active_briefing_and_its_pdf() {
    let mock = start_mock();
    let client = client(&mock);
    let asked = recorded("offices/get_briefing/examples/active.request.json");
    let office = asked["office_id"].as_str().expect("an office").to_string();
    let active = client
        .offices
        .get_briefing(
            weather_gov::offices::get_briefing::Request {
                office_id: office.clone(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_briefing");
    let briefing = active.briefing.expect("a briefing out");
    assert_eq!(briefing.office_id, office);
    assert!(briefing.start_time < briefing.end_time);
    assert_eq!(
        briefing.download,
        format!(
            "https://api.weather.gov/offices/{office}/briefing/download/{}",
            briefing.id
        )
    );
}

#[tokio::test]
async fn offices_get_briefing_answers_an_honest_null_for_an_office_with_none() {
    let mock = start_mock();
    let client = client(&mock);
    let active = client
        .offices
        .get_briefing(
            weather_gov::offices::get_briefing::Request {
                office_id: "SEW".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_briefing");
    assert!(active.briefing.is_none());
}

#[tokio::test]
async fn offices_list_headlines_links_each_headline() {
    let mock = start_mock();
    let client = client(&mock);
    let headlines = client
        .offices
        .list_headlines(
            weather_gov::offices::list_headlines::Request {
                office_id: "AKQ".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_headlines");
    assert!(!headlines.graph.is_empty());
    for headline in &headlines.graph {
        assert_eq!(headline.office, "https://api.weather.gov/offices/AKQ");
        // `@id` renders as `id` and the headline id as `id2`, as on `Zone`.
        assert_eq!(
            headline.id,
            format!("{}/headlines/{}", headline.office, headline.id2)
        );
        assert!(headline.content.contains(&headline.title));
    }
}

#[tokio::test]
async fn offices_get_headline_returns_the_headline_the_office_lists() {
    let mock = start_mock();
    let client = client(&mock);
    let asked = recorded("offices/get_headline/examples/wakefield.request.json");
    let id = asked["headline_id"]
        .as_str()
        .expect("a headline")
        .to_string();
    let headline = client
        .offices
        .get_headline(
            weather_gov::offices::get_headline::Request {
                office_id: asked["office_id"].as_str().expect("an office").to_string(),
                headline_id: id.clone(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_headline");
    assert_eq!(headline.id2, id);
    let listed = payload("offices/list_headlines/examples/wakefield.response.json")["@graph"]
        .as_array()
        .expect("a graph")
        .iter()
        .find(|entry| entry["id"] == id.as_str())
        .expect("the office lists it")
        .clone();
    assert_eq!(listed["title"], headline.title.as_str());
    assert_eq!(listed["link"], headline.link.as_str());
}

#[tokio::test]
async fn offices_list_weather_stories_returns_each_graphic_with_its_text() {
    let mock = start_mock();
    let client = client(&mock);
    let stories = client
        .offices
        .list_weather_stories(
            weather_gov::offices::list_weather_stories::Request {
                office_id: "AKQ".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_weather_stories")
        .stories;
    assert!(!stories.is_empty());
    for story in &stories {
        assert_eq!(story.office_id, "AKQ");
        assert!(!story.title.is_empty() && !story.description.is_empty());
        assert!(story.start_time < story.end_time);
        if let Some(download) = &story.download {
            assert!(download
                .starts_with("https://api.weather.gov/offices/AKQ/weatherstories/download/"));
        }
    }
}

#[tokio::test]
async fn radio_list_transmitters_last_page_is_short_with_no_next_page() {
    let mock = start_mock();
    let client = client(&mock);
    let asked = recorded("radio/list_transmitters/examples/last_page.request.json");
    let page = client
        .radio
        .list_transmitters(
            weather_gov::radio::list_transmitters::Request {
                cursor: Some(asked["cursor"].as_str().expect("a cursor").to_string()),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("list_transmitters");
    assert!(!page.graph.is_empty() && page.graph.len() < 500);
    assert!(page.pagination.is_none());
    let calls: std::collections::HashSet<_> = page.graph.iter().map(|t| &t.call_sign).collect();
    assert!(calls.len() < page.graph.len());
    for transmitter in &page.graph {
        assert_eq!(
            transmitter.id,
            format!("https://api.weather.gov/radio/{}", transmitter.call_sign)
        );
        assert_eq!(
            transmitter.same_codes.as_ref().map(Vec::len),
            Some(transmitter.counties.len())
        );
        assert!(transmitter
            .transmitter_frequency
            .as_str()
            .starts_with("162."));
    }
}

#[tokio::test]
async fn radio_get_transmitter_returns_the_one_the_county_lists() {
    let mock = start_mock();
    let client = client(&mock);
    let transmitter = client
        .radio
        .get_transmitter(
            weather_gov::radio::get_transmitter::Request {
                call_sign: "KHB60".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .expect("get_transmitter");
    assert_eq!(transmitter.call_sign, "KHB60");
    assert_eq!(transmitter.id, "https://api.weather.gov/radio/KHB60");
    let county = payload("zones/list_transmitters/examples/king_county.response.json")["@graph"]
        .as_array()
        .expect("a graph")
        .iter()
        .find(|entry| entry["callSign"] == "KHB60")
        .expect("King County lists it")
        .clone();
    let counties: Vec<&str> = county["counties"]
        .as_array()
        .expect("counties")
        .iter()
        .map(|c| c.as_str().expect("a county"))
        .collect();
    assert_eq!(transmitter.counties, counties);
    assert_eq!(
        transmitter.transmitter_frequency.as_str(),
        county["transmitterFrequency"]
            .as_str()
            .expect("a frequency")
    );
}
