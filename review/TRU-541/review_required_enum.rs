//! The shortest literal a user can write for `list_zones_by_type` with one filter.
//! Known: fails E0277 until TRU-526 (no `Default` on a request with a required enum).
use weather_gov::types::ZoneKind;
use weather_gov::zones::list_zones_by_type::Request;

pub fn washington_counties() -> Request {
    Request {
        zone_type: ZoneKind::County,
        area: Some(vec!["WA".to_string()]),
        ..Default::default()
    }
}
