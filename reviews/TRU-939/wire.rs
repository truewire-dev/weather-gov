//! Review-only consumer tests: copy into the isolated package's tests/ directory.
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::thread;

use truewire_core::{serde_json::json, CallOptions};
use weather_gov::{core::CoreOptions, Weather};

fn capture() -> (Weather, thread::JoinHandle<String>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let worker = thread::spawn(move || {
        let (mut socket, _) = listener.accept().unwrap();
        socket.set_read_timeout(Some(std::time::Duration::from_secs(10))).unwrap();
        let mut reader = BufReader::new(socket.try_clone().unwrap());
        let mut first = String::new();
        reader.read_line(&mut first).unwrap();
        loop {
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            if line == "\r\n" || line.is_empty() { break; }
        }
        socket.write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}").unwrap();
        first.split_whitespace().nth(1).unwrap().to_owned()
    });
    (Weather::with_options(CoreOptions::new("review@truewire.dev").base_url(base)), worker)
}

fn assert_wire(worker: thread::JoinHandle<String>, path: &str, expected: &[&str]) {
    let target = worker.join().unwrap();
    let (actual_path, query) = target.split_once('?').unwrap();
    assert_eq!(actual_path, path);
    let mut actual: Vec<_> = query.split('&').collect();
    let mut expected = expected.to_vec();
    actual.sort();
    expected.sort();
    assert_eq!(actual, expected);
}

#[tokio::test]
async fn stations_empty_arrays_scalars_and_extension_booleans() {
    let (client, worker) = capture();
    let mut request = weather_gov::stations::list_stations::Request {
        id: Some(vec![]), state: Some(vec![]), limit: Some(2),
        cursor: Some("a+b&c".into()), ..Default::default()
    };
    request.extra.insert("flag".into(), json!(false));
    request.extra.insert("flags".into(), json!([true, false]));
    request.extra.insert("absent".into(), json!(null));
    client.stations.list_stations_raw(request, CallOptions::default()).await.unwrap();
    assert_wire(worker, "/stations", &["cursor=a%2Bb%26c", "flag=false", "flags=true%2Cfalse", "limit=2"]);
}

#[tokio::test]
async fn zones_enum_arrays_and_scalar_comma() {
    let (client, worker) = capture();
    let request = weather_gov::zones::list_zones::Request {
        id: Some(vec!["WAZ315".into(), "WAC033".into()]),
        type_: Some(vec![weather_gov::types::ZoneKind::Forecast, weather_gov::types::ZoneKind::County]),
        point: Some("47.6,-122.3".into()), ..Default::default()
    };
    client.zones.list_zones_raw(request, CallOptions::default()).await.unwrap();
    assert_wire(worker, "/zones", &["id=WAZ315%2CWAC033", "type=forecast%2Ccounty", "point=47.6%2C-122.3"]);
}

#[tokio::test]
async fn alerts_enum_and_string_arrays() {
    use weather_gov::alerts::get_active_alerts::{Request, RequestSeverityItem};
    let (client, worker) = capture();
    let request = Request {
        area: Some(vec!["WA".into(), "OR".into()]),
        severity: Some(vec![RequestSeverityItem::Severe, RequestSeverityItem::Moderate]),
        ..Default::default()
    };
    client.alerts.get_active_alerts_raw(request, CallOptions::default()).await.unwrap();
    assert_wire(worker, "/alerts/active", &["area=WA%2COR", "severity=Severe%2CModerate"]);
}

#[tokio::test]
async fn zones_by_type_path_stays_separate() {
    let (client, worker) = capture();
    let request = weather_gov::zones::list_zones_by_type::Request {
        zone_type: weather_gov::types::ZoneKind::County,
        id: Some(vec!["WAC033".into(), "WAC061".into()]),
        area: None, region: None, point: None, effective: None, limit: None,
        extra: Default::default(),
    };
    client.zones.list_zones_by_type_raw(request, CallOptions::default()).await.unwrap();
    assert_wire(worker, "/zones/county", &["id=WAC033%2CWAC061"]);
}
