use futures::StreamExt;
use truewire_core::{CallOptions, TimestampIso};
use weather_gov::core::CoreOptions;
use weather_gov::{stations, Weather};

fn ts(s: &str) -> TimestampIso {
    truewire_core::serde_json::from_value(truewire_core::serde_json::json!(s)).unwrap()
}

#[tokio::main]
async fn main() {
    let client = Weather::with_options(CoreOptions::new("r@r").base_url("http://127.0.0.1:8765".to_string()));
    for limit in [Some(10), Some(7), Some(2), None, Some(1000), Some(1), Some(0), Some(-1)] {
        let req = stations::get_observations::Request {
            station_id: "KSEA".into(),
            start: Some(ts("2026-09-09T02:00:00Z")),
            end: Some(ts("2026-09-09T08:00:00Z")),
            limit,
            ..Default::default()
        };
        println!("== limit {limit:?}");
        match client.stations.get_observations_paged(req, CallOptions::default()).await {
            Ok(rows) => {
                let mut stamps: Vec<_> = rows.iter().map(|r| r.properties.timestamp.0).collect();
                let n = stamps.len();
                let sorted_desc = stamps.windows(2).all(|w| w[0] > w[1]);
                stamps.dedup();
                println!("   rows {n}, distinct {}, strictly newest-first {sorted_desc}", stamps.len());
            }
            Err(e) => println!("   ERR {e}"),
        }
    }
    // pages(): checkpoint and resume from a saved state
    let req = stations::get_observations::Request {
        station_id: "KSEA".into(),
        start: Some(ts("2026-09-09T02:00:00Z")),
        end: Some(ts("2026-09-09T08:00:00Z")),
        limit: Some(30),
        ..Default::default()
    };
    let walk = client.stations.get_observations_paged(req, CallOptions::default());
    let mut pages = walk.pages();
    let first = pages.next().await.unwrap().unwrap();
    println!("== pages: first {} rows, next pos {:?}, carried {}", first.rows.len(), first.next.as_ref().map(|s| s.pos), first.next.as_ref().map_or(0, |s| s.carried.len()));
    drop(pages);
    let rest = walk.resume(first.next.unwrap()).await.unwrap();
    println!("   resumed: {} more rows, total {}", rest.len(), first.rows.len() + rest.len());
}
