use truewire_core::serde_json::{self, json, Value};
use weather_gov::offices::{get_briefing::ActiveBriefing, list_weather_stories::WeatherStory};
use weather_gov::types::{OfficeHeadline, QuantitativeValue};

fn payload(path: &str) -> Value {
    let root = std::env::var("REVIEW_CLIENT_ROOT").expect("REVIEW_CLIENT_ROOT");
    let text = std::fs::read_to_string(format!("{root}/spec/endpoints/{path}")).unwrap();
    serde_json::from_str::<Value>(&text).unwrap()["payload"].clone()
}

#[test]
fn required_nullable_fields_reject_missing_and_accept_null() {
    let briefing: ActiveBriefing = serde_json::from_value(json!({"briefing": null})).unwrap();
    assert!(briefing.briefing.is_none());
    assert!(serde_json::from_value::<ActiveBriefing>(json!({})).is_err());
    let mut headline = payload("offices/get_headline/examples/wakefield.response.json");
    let h: OfficeHeadline = serde_json::from_value(headline.clone()).unwrap();
    assert_eq!(h.id, "8c67c3a1e638b30d1d9dd1524ab53330");
    assert!(h.at_id.ends_with(&h.id));
    assert!(h.summary.is_none());
    headline.as_object_mut().unwrap().remove("summary");
    assert!(serde_json::from_value::<OfficeHeadline>(headline).is_err());
    let mut story = payload("offices/list_weather_stories/examples/wakefield.response.json")["stories"][0].clone();
    story["download"] = Value::Null;
    assert!(serde_json::from_value::<WeatherStory>(story.clone()).unwrap().download.is_none());
    story.as_object_mut().unwrap().remove("download");
    assert!(serde_json::from_value::<WeatherStory>(story).is_err());
    assert!(serde_json::from_value::<QuantitativeValue>(json!({"unitCode":"wmoUnit:degC"})).is_err());
    assert!(serde_json::from_value::<QuantitativeValue>(json!({"unitCode":"wmoUnit:degC", "value":null})).unwrap().value.is_none());
}

#[test]
fn taf_and_headline_graphs_roundtrip_recorded_wire_keys() {
    use weather_gov::stations::list_tafs::TafCollection;
    use weather_gov::offices::list_headlines::OfficeHeadlineCollection;
    let wire = payload("stations/list_tafs/examples/ksea.response.json");
    let collection: TafCollection = serde_json::from_value(wire.clone()).unwrap();
    assert!(!collection.at_graph.is_empty());
    assert_eq!(serde_json::to_value(collection).unwrap(), wire);
    let wire = payload("offices/list_headlines/examples/wakefield.response.json");
    let collection: OfficeHeadlineCollection = serde_json::from_value(wire.clone()).unwrap();
    assert!(!collection.at_graph.is_empty());
    assert_eq!(serde_json::to_value(collection).unwrap(), wire);
}
