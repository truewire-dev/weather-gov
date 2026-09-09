//! The README's examples, compiled — and checked against the README, character for
//! character.
//!
//! `truewire docs check` type-checks the Python examples with pyright, and the TypeScript
//! package extracts its own README blocks and runs `tsc` over them. Rust has neither, and
//! a crate whose `lib.rs` is generated cannot carry `#![doc = include_str!("README.md")]`
//! to get doc tests for free.
//!
//! So the blocks live here, each in its own module, which is what makes `cargo test`
//! compile them. Nothing runs; compiling is the whole point. What keeps this from drifting
//! away from the page is the test at the bottom: every ```rust block in the README has to
//! appear in this file verbatim, so an example cannot be fixed in one place and left
//! rotting in the other.

use std::path::Path;

mod readme_1 {
    #![allow(dead_code, unused_imports, unused_variables)]

use std::sync::Arc;

use truewire_core::CallOptions;
use weather_gov::core::{Core, CoreOptions};
use weather_gov::{forecast, points, Weather};

#[tokio::main]
async fn main() -> truewire_core::Result<()> {
    let client = Weather::new(Arc::new(Core::new(CoreOptions::new("you@example.com"))));

    let point = client
        .points
        .get_point(
            points::get_point::Request { latitude: 47.6062, longitude: -122.3321, ..Default::default() },
            CallOptions::default(),
        )
        .await?;
    println!("{} {},{} {}", point.grid_id, point.grid_x, point.grid_y, point.time_zone);

    let forecast = client
        .forecast
        .get_forecast(
            forecast::get_forecast::Request {
                office: point.grid_id.clone(),
                grid_x: point.grid_x,
                grid_y: point.grid_y,
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await?;
    for period in forecast.periods.iter().take(3) {
        // `{:?}` on the unit: a generated enum derives Debug, not Display.
        println!("{:<16} {}°{:?}  {}", period.name, period.temperature, period.temperature_unit, period.short_forecast);
    }
    Ok(())
}
}

mod readme_2 {
    #![allow(dead_code, unused_imports, unused_variables)]

use std::sync::Arc;
use std::time::Duration;

use truewire_core::CallOptions;
use weather_gov::core::{Core, CoreOptions};
use weather_gov::{alerts, Weather};

async fn severe(client: &Weather) -> truewire_core::Result<usize> {
    let page = client
        .alerts
        .get_active_alerts(
            alerts::get_active_alerts::Request {
                status: Some(vec![alerts::get_active_alerts::RequestStatusItem::Actual]),
                severity: Some(vec![alerts::get_active_alerts::RequestSeverityItem::Severe]),
                ..Default::default()
            },
            CallOptions { timeout: Some(Duration::from_secs(5)), ..Default::default() },
        )
        .await?;
    Ok(page.features.len())
}

async fn build() -> truewire_core::Result<()> {
    let client = Weather::new(Arc::new(Core::new(CoreOptions::new("you@example.com"))));
    println!("{} severe alerts", severe(&client).await?);
    Ok(())
}
}

mod readme_3 {
    #![allow(dead_code, unused_imports, unused_variables)]

use truewire_core::CallOptions;
use weather_gov::{stations, Weather};

async fn conditions(client: &Weather) -> truewire_core::Result<()> {
    let now = client
        .stations
        .get_latest_observation(
            stations::get_latest_observation::Request {
                station_id: "KSEA".to_string(),
                ..Default::default()
            },
            CallOptions::default(),
        )
        .await?;
    println!("{:?} at {}", now.station_name, now.timestamp.0);
    println!("  temperature {:?} {}", now.temperature.value, now.temperature.unit_code);
    match now.wind_gust.as_ref().and_then(|gust| gust.value) {
        Some(gust) => println!("  gusting to {gust} km/h"),
        None => println!("  not gusting"),
    }
    Ok(())
}
}

/// Every ```rust block in the README appears in this file, exactly as written.
///
/// The direction matters: the README is the source, and this file mirrors it. A block
/// edited on the page and not here fails, which is the drift worth catching -- a reader
/// copies from the page.
#[test]
fn every_readme_example_is_compiled_here() {
    let readme = std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("README.md"))
        .expect("the package README");
    let source = include_str!("readme_examples.rs");

    let mut blocks = Vec::new();
    let mut rest = readme.as_str();
    while let Some(start) = rest.find("```rust\n") {
        let body = &rest[start + "```rust\n".len()..];
        let end = body.find("\n```").expect("an unterminated ```rust block in the README");
        blocks.push(&body[..end + 1]);
        rest = &body[end..];
    }

    assert!(!blocks.is_empty(), "the README has no rust examples to compile");
    for (index, block) in blocks.iter().enumerate() {
        assert!(
            source.contains(*block),
            "README example {} is not compiled by this file. Copy it in verbatim, in its \
             own `mod readme_N`, or fix the copy that has drifted:\n\n{}",
            index + 1,
            block,
        );
    }
}
