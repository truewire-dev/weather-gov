//! TRU-528: one zone type across every request that takes one. Passes at 1b8a646.
use truewire_core::CallOptions;
use weather_gov::types::ZoneKind;
use weather_gov::zones::{get_forecast, get_zone, list_zones};
use weather_gov::Weather;

pub async fn public_zone_everywhere(client: &Weather, code: &str) -> truewire_core::Result<()> {
    let kind = ZoneKind::Public; // one value, three endpoints
    let _ = client
        .zones
        .list_zones(
            list_zones::Request { type_: Some(vec![kind]), ..Default::default() },
            CallOptions::default(),
        )
        .await?;
    let _ = client
        .zones
        .get_zone(
            get_zone::Request {
                zone_id: code.to_string(),
                zone_type: kind,
                effective: None,
                extra: Default::default(),
            },
            CallOptions::default(),
        )
        .await?;
    let _ = client
        .zones
        .get_forecast(
            get_forecast::Request { zone_id: code.to_string(), zone_type: kind, extra: Default::default() },
            CallOptions::default(),
        )
        .await?;
    Ok(())
}

// The TRU-513 conversion, now the identity.
pub fn same_concept(a: ZoneKind) -> weather_gov::types::ZoneKind {
    a
}
