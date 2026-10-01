//! TRU-605 review probes: what a user of the aviation group sees. Not part of the PR.

use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::mpsc;

use truewire_core::serde_json::{self, json, Value};
use truewire_core::{CallOptions, DateIso};
use weather_gov::aviation::{get_cwa, get_sigmet, list_sigmets};
use weather_gov::core::CoreOptions;
use weather_gov::types::{CenterWeatherAdvisoryFeature, CwsuId, Position, SigmetFeature};
use weather_gov::Weather;

/// A one-shot HTTP server: answers `body` and reports the request target it was asked for.
fn capture(body: Value) -> (String, mpsc::Receiver<String>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}", listener.local_addr().unwrap());
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
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
        tx.send(line.split(' ').nth(1).unwrap().to_string()).unwrap();
        let body = body.to_string();
        write!(
            stream,
            "HTTP/1.1 200 OK\r\nContent-Type: application/geo+json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body
        )
        .unwrap();
    });
    (url, rx)
}

fn client(url: String) -> Weather {
    Weather::with_options(CoreOptions::new("review@truewire.dev").base_url(url))
}

fn feature(properties: Value) -> Value {
    json!({"type": "Feature", "geometry": null, "properties": properties})
}

fn cwa() -> Value {
    feature(json!({
        "id": "https://api.weather.gov/aviation/cwsus/ZFW/cwas/2026-09-30/301",
        "issueTime": "2026-09-30T22:34:00+00:00", "cwsu": "ZFW", "sequence": 301,
        "start": "2026-09-30T22:34:00+00:00", "end": "2026-09-30T23:10:00+00:00",
        "observedProperty": null, "text": "ISOL TS D10"
    }))
}

fn sigmet() -> Value {
    feature(json!({
        "id": "https://api.weather.gov/aviation/sigmets/ANC/2026-09-30/2005",
        "issueTime": "2026-09-30T20:05:00+00:00", "fir": null, "atsu": "ANC",
        "sequence": null, "phenomenon": null,
        "start": "2026-09-30T20:15:00+00:00", "end": "2026-10-01T04:15:00+00:00"
    }))
}

#[tokio::test]
async fn paths_and_filters_on_the_wire() {
    let (url, seen) = capture(cwa());
    let date = DateIso(chrono_date(2026, 9, 30));
    client(url)
        .aviation
        .get_cwa(
            get_cwa::Request { cwsu_id: CwsuId::Zfw, date, sequence: 301, extra: Default::default() },
            CallOptions::default(),
        )
        .await
        .unwrap();
    assert_eq!(seen.recv().unwrap(), "/aviation/cwsus/ZFW/cwas/2026-09-30/301");

    let (url, seen) = capture(sigmet());
    client(url)
        .aviation
        .get_sigmet(
            get_sigmet::Request { atsu: "ANC".into(), date, time: "2005".into(), extra: Default::default() },
            CallOptions::default(),
        )
        .await
        .unwrap();
    assert_eq!(seen.recv().unwrap(), "/aviation/sigmets/ANC/2026-09-30/2005");

    let (url, seen) = capture(json!({"type": "FeatureCollection", "features": []}));
    client(url)
        .aviation
        .list_sigmets(list_sigmets::Request::default(), CallOptions::default())
        .await
        .unwrap();
    assert_eq!(seen.recv().unwrap(), "/aviation/sigmets", "no filter sends no query");

    let (url, seen) = capture(json!({"type": "FeatureCollection", "features": []}));
    let start: truewire_core::TimestampIso =
        serde_json::from_value(json!("2026-09-30T12:00:00+00:00")).unwrap();
    client(url)
        .aviation
        .list_sigmets(
            list_sigmets::Request { start: Some(start), sequence: Some("1E".into()), ..Default::default() },
            CallOptions::default(),
        )
        .await
        .unwrap();
    println!("list_sigmets(start, sequence) -> {}", seen.recv().unwrap());
}

fn chrono_date(y: i32, m: u32, d: u32) -> truewire_core::chrono::NaiveDate {
    truewire_core::chrono::NaiveDate::from_ymd_opt(y, m, d).unwrap()
}

#[test]
fn nulls_decode_and_stay_on_the_wire() {
    let advisory: CenterWeatherAdvisoryFeature = serde_json::from_value(cwa()).unwrap();
    assert!(advisory.geometry.is_none() && advisory.properties.observed_property.is_none());
    let back = serde_json::to_value(&advisory).unwrap();
    assert_eq!(back["geometry"], Value::Null);
    assert!(back["properties"].as_object().unwrap().contains_key("observedProperty"));
    println!("issueTime re-dumped: {}", back["properties"]["issueTime"]);

    let message: SigmetFeature = serde_json::from_value(sigmet()).unwrap();
    assert!(message.properties.fir.is_none() && message.properties.sequence.is_none());
}

/// From a listed SIGMET to the request that fetches it alone: what a user types.
#[test]
fn list_item_to_get_sigmet_request() {
    let message: SigmetFeature = serde_json::from_value(sigmet()).unwrap();
    let s = &message.properties;
    let request = get_sigmet::Request {
        atsu: s.atsu.clone(),
        date: DateIso::from_datetime(&s.issue_time),
        time: s.issue_time.format("%H%M").to_string(),
        extra: Default::default(),
    };
    assert_eq!(serde_json::to_value(&request).unwrap(), json!({"atsu": "ANC", "date": "2026-09-30", "time": "2005"}));
}

/// A latitude-first advisory corner is the same Rust type as a longitude-first GeoJSON
/// `Position`, so nothing stops one being passed where the other is meant.
#[test]
fn advisory_corner_is_a_geojson_position() {
    fn plot_geojson(position: Position) -> (f64, f64) {
        let (longitude, latitude) = position;
        (longitude, latitude)
    }
    let mut value = cwa();
    value["geometry"] = json!({"type": "Polygon", "coordinates": [[[35.203, -99.902], [34.822, -98.492], [32.28, -97.742], [35.203, -99.902]]]});
    let advisory: CenterWeatherAdvisoryFeature = serde_json::from_value(value).unwrap();
    let corner = advisory.geometry.unwrap().coordinates[0][0];
    let (longitude, latitude) = plot_geojson(corner);
    assert_eq!((longitude, latitude), (35.203, -99.902), "compiles, and is transposed");
}
