//! A zone the service answered with, fed back as a request. Known: fails until the shared
//! record field `Zone.type` renders as `ZoneKind` (TRU-525/TRU-535, typed PR #75 for `id2`).
use truewire_core::CallOptions;
use weather_gov::zones::{get_forecast, list_zones};
use weather_gov::Weather;

pub async fn forecasts_at(client: &Weather, point: &str) -> truewire_core::Result<()> {
    let page = client
        .zones
        .list_zones(
            list_zones::Request { point: Some(point.to_string()), ..Default::default() },
            CallOptions::default(),
        )
        .await?;
    for feature in page.features {
        let zone = feature.properties;
        client
            .zones
            .get_forecast(
                get_forecast::Request { zone_id: zone.id2, zone_type: zone.type_2, extra: Default::default() },
                CallOptions::default(),
            )
            .await?;
    }
    Ok(())
}
