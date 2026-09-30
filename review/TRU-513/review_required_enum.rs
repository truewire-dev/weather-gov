//! The shortest literal a user can write for `list_zones_by_type` with one filter.
use weather_gov::zones::list_zones_by_type::{Request, RequestZoneType};

pub fn washington_counties() -> Request {
    Request {
        zone_type: RequestZoneType::County,
        area: Some(vec!["WA".to_string()]),
        ..Default::default()
    }
}
