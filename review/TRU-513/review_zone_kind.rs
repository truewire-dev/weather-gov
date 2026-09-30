//! A user lists the zones at a point, then asks for each public zone's text forecast.
use weather_gov::zones::{get_forecast, list_zones};
use weather_gov::Weather;
use truewire_core::CallOptions;

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
                get_forecast::Request {
                    zone_type: zone.type_2, // the type the service just answered with
                    zone_id: zone.id2,
                    extra: Default::default(),
                },
                CallOptions::default(),
            )
            .await?;
    }
    Ok(())
}

// The same enum again, four times over: one zone type, five Rust types.
pub fn same_concept(
    a: weather_gov::zones::get_zone::RequestZoneType,
) -> weather_gov::zones::list_zones_by_type::RequestZoneType {
    a
}
