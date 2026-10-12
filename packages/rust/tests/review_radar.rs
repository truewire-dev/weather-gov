//! TRU-616 review: what the radar surfaces put on the wire, and what a 404 becomes.
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::mpsc;

use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::radar;
use weather_gov::Weather;

/// Answers each connection with `status` and `body`, and sends back the request line.
fn server(status: &'static str, body: &'static str) -> (String, mpsc::Receiver<String>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut reader = BufReader::new(stream.try_clone().unwrap());
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            loop {
                let mut h = String::new();
                reader.read_line(&mut h).unwrap();
                if h == "\r\n" || h.is_empty() {
                    break;
                }
            }
            tx.send(line.trim_end().to_string()).ok();
            write!(stream, "HTTP/1.1 {status}\r\ncontent-type: application/json\r\ncontent-length: {}\r\nconnection: close\r\n\r\n{body}", body.len()).unwrap();
        }
    });
    (url, rx)
}

fn client(url: &str) -> Weather {
    Weather::with_options(CoreOptions::new("review@truewire.dev").base_url(url.to_string()))
}

#[tokio::test]
async fn wire_forms() {
    let (url, rx) = server("200 OK", "{}");
    let c = client(&url);
    let _ = c
        .radar
        .get_profiler(
            radar::get_profiler::Request {
                station_id: "TLKA2".into(),
                time: Some("2026-09-30T23:00:00Z/PT1H".into()),
                interval: Some("PT1H".into()),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("get_profiler: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .get_profiler(
            radar::get_profiler::Request::default(),
            CallOptions::default(),
        )
        .await;
    println!("get_profiler default: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .get_queue(
            radar::get_queue::Request {
                host: radar::get_queue::RequestHost::Tds,
                limit: Some(5),
                arrived: None,
                created: Some("2026-09-30T23:00:00Z/PT10M".into()),
                published: None,
                station: None,
                type_: None,
                feed: None,
                resolution: Some(8),
                extra: Default::default(),
            },
            CallOptions::default(),
        )
        .await;
    println!("get_queue: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .list_stations(
            radar::list_stations::Request {
                station_type: Some(vec!["TDWR".into(), "Profiler".into()]),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("list_stations: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .list_stations(
            radar::list_stations::Request {
                station_type: Some(vec![]),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("list_stations empty vec: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .list_station_alarms(
            radar::list_station_alarms::Request {
                station_id: "KATX".into(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("list_station_alarms: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .get_station(
            radar::get_station::Request {
                station_id: "KATX".into(),
                reporting_host: Some("rdss".into()),
                host: Some("ldm1".into()),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("get_station: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .list_spgds(
            radar::list_spgds::Request {
                published: Some("2026-09-30T12:00:00Z/PT1M".into()),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("list_spgds: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .list_servers(Default::default(), CallOptions::default())
        .await;
    println!("list_servers: {}", rx.recv().unwrap());
    let _ = c
        .radar
        .get_server(
            radar::get_server::Request {
                server_id: "ldm1".into(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await;
    println!("get_server: {}", rx.recv().unwrap());
}

#[tokio::test]
async fn profiler_404() {
    let (url, _rx) = server(
        "404 Not Found",
        r#"{"correlationId":"x","title":"Not Found","type":"https://api.weather.gov/problems/NotFound","status":404,"detail":"Not Found","instance":"https://api.weather.gov/requests/x"}"#,
    );
    let e = client(&url)
        .radar
        .get_profiler(
            radar::get_profiler::Request {
                station_id: "TLKA2".into(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await
        .unwrap_err();
    println!("404 -> {e}\n{e:?}");
}

fn roundtrip<T: serde::de::DeserializeOwned + serde::Serialize>(file: &str) {
    let path = format!(
        "{}/../../spec/endpoints/radar/{file}",
        env!("CARGO_MANIFEST_DIR")
    );
    let v: truewire_core::serde_json::Value =
        truewire_core::serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
    let body = v["payload"].clone();
    let typed: T = truewire_core::serde_json::from_value(body.clone())
        .unwrap_or_else(|e| panic!("{file}: {e}"));
    let back = truewire_core::serde_json::to_value(&typed).unwrap();
    let mut diffs = Vec::new();
    diff("", &body, &back, &mut diffs);
    if diffs.is_empty() {
        println!("{file}: lossless");
    } else {
        let odd: Vec<_> = diffs
            .iter()
            .filter(|d| {
                !(d.contains("+00:00\" rust")
                    || d.ends_with(".0")
                        && d.split(" rust ").next().map_or(false, |w| !w.contains('.')))
            })
            .collect();
        println!(
            "{file}: {} differences, {} not +00:00->Z or int->float: {:?}",
            diffs.len(),
            odd.len(),
            odd
        );
    }
}

fn diff(
    at: &str,
    a: &truewire_core::serde_json::Value,
    b: &truewire_core::serde_json::Value,
    out: &mut Vec<String>,
) {
    use truewire_core::serde_json::Value::*;
    match (a, b) {
        (Object(x), Object(y)) => {
            for (k, v) in x {
                match y.get(k) {
                    Some(w) => diff(&format!("{at}/{k}"), v, w, out),
                    None => out.push(format!("{at}/{k} dropped")),
                }
            }
            for k in y.keys() {
                if !x.contains_key(k) {
                    out.push(format!("{at}/{k} added: {}", y[k]))
                }
            }
        }
        (Array(x), Array(y)) if x.len() == y.len() => {
            for (i, (v, w)) in x.iter().zip(y).enumerate() {
                diff(&format!("{at}/{i}"), v, w, out)
            }
        }
        _ if a != b => out.push(format!("{at}: wire {a} rust {b}")),
        _ => {}
    }
}

#[test]
fn recordings_roundtrip() {
    roundtrip::<radar::get_queue::RadarQueue>("get_queue/examples/seattle_capped.response.json");
    roundtrip::<radar::list_spgds::SpgdsCollection>("list_spgds/examples/one_minute.response.json");
    roundtrip::<radar::list_stations::RadarStationCollection>(
        "list_stations/examples/profilers.response.json",
    );
    roundtrip::<radar::list_servers::RadarServerCollection>(
        "list_servers/examples/all.response.json",
    );
    roundtrip::<weather_gov::types::RadarServer>("get_server/examples/ldm1.response.json");
    roundtrip::<weather_gov::types::RadarStationFeature>(
        "get_station/examples/seattle.response.json",
    );
    roundtrip::<radar::list_station_alarms::RadarAlarmCollection>(
        "list_station_alarms/examples/seattle.response.json",
    );
    roundtrip::<radar::list_stations::RadarStationCollection>(
        "list_stations/examples/tdwr_and_profilers.response.json",
    );
}
