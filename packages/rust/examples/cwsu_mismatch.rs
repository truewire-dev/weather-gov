//! TRU-605: does the advisory's own unit compare with the unit the user asked for?
use weather_gov::aviation::list_cwas;
use weather_gov::types::CenterWeatherAdvisoryCollection;

fn from_unit(asked: &list_cwas::Request, page: &CenterWeatherAdvisoryCollection) -> bool {
    page.features.iter().all(|f| f.properties.cwsu == asked.cwsu_id)
}

fn main() {
    let _ = from_unit;
}
