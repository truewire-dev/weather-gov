use futures::StreamExt; // `futures` in your Cargo.toml: `rows()` is a `Stream`
use truewire_core::{chrono::Utc, CallOptions, TimestampIso};
use weather_gov::{stations, Weather};

async fn yesterday(client: &Weather) -> truewire_core::Result<()> {
    let now = Utc::now();
    let request = stations::get_observations::Request {
        station_id: "KSEA".to_string(),
        start: Some(TimestampIso(now - truewire_core::chrono::Duration::days(1))),
        end: Some(TimestampIso(now)),
        ..Default::default()
    };
    let walk = client.stations.get_observations_paged(request, CallOptions::default());

    // Every observation in the span, newest first:
    let all = walk.clone().await?;
    println!("{} observations", all.len());

    // Or one response at a time:
    let mut pages = walk.rows();
    while let Some(page) = pages.next().await {
        println!("{} more", page?.len());
    }
    Ok(())
}

fn main() { let _ = yesterday; }
