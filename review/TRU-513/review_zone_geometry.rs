//! A user writes one helper over the shared `ZoneGeometry` schema the spec declares.
use weather_gov::types::{ZoneFeature, ZoneGeometry};

fn has_outline(geometry: &ZoneGeometry) -> bool {
    geometry.is_some()
}

pub fn check(feature: &ZoneFeature) -> bool {
    has_outline(&feature.geometry)
}
