//! TRU-96, live: the paged walker still sends the caller's `limit` unclamped.
use truewire_core::serde_json::{from_value, json};
use weather_gov::core::CoreOptions;
use weather_gov::stations::get_observations::Request;
use weather_gov::{CallOptions, Weather};

#[tokio::main]
async fn main() {
    let client = Weather::with_options(CoreOptions::new("hello@truewire.dev"));
    for limit in [500, 1000] {
        let request = Request {
            station_id: "KSEA".into(),
            start: Some(from_value(json!("2026-09-28T00:00:00Z")).unwrap()),
            limit: Some(limit),
            ..Default::default()
        };
        match client.stations.get_observations_paged(request, CallOptions::default()).await {
            Ok(rows) => println!("limit={limit}: Ok({} rows)", rows.len()),
            Err(error) => println!("limit={limit}: Err({error})"),
        }
    }
}
