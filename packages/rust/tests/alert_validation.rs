//! Offline mutations of a recorded alert, never live recording evidence.
use truewire_core::serde_json::{self, json, Value};
use weather_gov::types::Alert;

fn alert() -> Value {
    let page: Value = serde_json::from_str(include_str!(
        "../../../spec/endpoints/alerts/list_alerts/examples/first_page.response.json"
    ))
    .unwrap();
    page["payload"]["features"][0]["properties"].clone()
}

#[test]
fn explicit_nulls_are_preserved() {
    for field in ["description", "response"] {
        let mut body = alert();
        body[field] = Value::Null;
        let parsed: Alert = serde_json::from_value(body).unwrap();
        let wire = serde_json::to_value(parsed).unwrap();
        assert!(wire.get(field).is_some(), "{field} must not disappear");
        assert_eq!(wire[field], Value::Null);
    }
}

#[test]
fn non_null_values_and_requiredness_are_preserved() {
    let mut body = alert();
    body["description"] = json!("Take shelter.");
    body["response"] = json!("Shelter");
    let parsed: Alert = serde_json::from_value(body.clone()).unwrap();
    let wire = serde_json::to_value(parsed).unwrap();
    assert_eq!(wire["description"], "Take shelter.");
    assert_eq!(wire["response"], "Shelter");
    body.as_object_mut().unwrap().remove("response");
    let parsed: Alert = serde_json::from_value(body.clone()).unwrap();
    assert!(serde_json::to_value(parsed).unwrap().get("response").is_none());
    body.as_object_mut().unwrap().remove("description");
    assert!(serde_json::from_value::<Alert>(body).is_err());
}

#[test]
fn invalid_non_null_values_still_fail() {
    for (field, value) in [
        ("description", json!(42)),
        ("description", json!({})),
        ("response", json!("shelter")),
        ("response", json!(42)),
    ] {
        let mut body = alert();
        body[field] = value;
        assert!(serde_json::from_value::<Alert>(body).is_err(), "{field}");
    }
}
