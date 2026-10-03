use truewire_core::serde_json::{self, json, Value};
use weather_gov::products::list_product_types::ProductTypeCollection;
use weather_gov::types::{
    AlertFeature, AlertGeometry, AlertGeometryValue, Zone, ZoneFeature, ZoneGeometry,
    ZoneGeometryValue, ZoneKind,
};

fn has_outline(geometry: &ZoneGeometry) -> bool {
    geometry.is_some()
}

fn is_public(kind: &ZoneKind) -> bool {
    *kind == ZoneKind::Public
}

fn zone_wire() -> Value {
    json!({
        "@id": "https://api.weather.gov/zones/forecast/WAZ558",
        "@type": "wx:Zone", "id": "WAZ558", "type": "public", "name": "Seattle",
        "effectiveDate": "2026-01-01T00:00:00Z",
        "expirationDate": "2200-01-01T00:00:00Z"
    })
}

fn polygon() -> Value {
    json!({"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0],
        [1.0, 1.0], [0.0, 0.0]]]})
}

#[test]
fn zone_geometry_and_kind_use_public_shared_types() {
    let zone: Zone = serde_json::from_value(zone_wire()).unwrap();
    assert!(is_public(&zone.type_));
    let wire = serde_json::to_value(&zone).unwrap();
    assert_eq!(wire["type"], "public");
    assert_eq!(wire["@type"], "wx:Zone");
    assert_eq!(wire["id"], "WAZ558");
    assert_eq!(wire["@id"], zone.at_id);
    assert!(wire.get("type_").is_none());

    let mut wire = json!({"id": zone.at_id, "type": "Feature", "properties": zone_wire(),
        "geometry": null});
    let feature: ZoneFeature = serde_json::from_value(wire.clone()).unwrap();
    assert!(!has_outline(&feature.geometry));
    assert!(serde_json::to_value(feature).unwrap()["geometry"].is_null());
    wire["geometry"] = polygon();
    let feature: ZoneFeature = serde_json::from_value(wire.clone()).unwrap();
    assert!(has_outline(&feature.geometry));
    assert!(matches!(
        feature.geometry,
        Some(ZoneGeometryValue::PolygonGeometry(_))
    ));
    assert_eq!(
        serde_json::to_value(feature).unwrap()["geometry"],
        polygon()
    );
    wire.as_object_mut().unwrap().remove("geometry");
    assert!(serde_json::from_value::<ZoneFeature>(wire).is_err());
}

#[test]
fn alert_geometry_preserves_missing_null_and_value() {
    let recording: Value = serde_json::from_str(include_str!(
        "../../../spec/endpoints/alerts/get_alert/examples/one.response.json"
    ))
    .unwrap();
    let mut wire = recording["payload"].clone();
    wire.as_object_mut().unwrap().remove("geometry");
    let missing: AlertFeature = serde_json::from_value(wire.clone()).unwrap();
    let geometry: &Option<AlertGeometry> = &missing.geometry;
    assert!(geometry.is_none());
    assert!(serde_json::to_value(missing)
        .unwrap()
        .get("geometry")
        .is_none());

    wire["geometry"] = Value::Null;
    let null: AlertFeature = serde_json::from_value(wire.clone()).unwrap();
    assert!(matches!(null.geometry, Some(None)));
    let encoded = serde_json::to_value(null).unwrap();
    assert_eq!(encoded.get("geometry"), Some(&Value::Null));

    wire["geometry"] = polygon();
    let value: AlertFeature = serde_json::from_value(wire).unwrap();
    assert!(matches!(
        value.geometry,
        Some(Some(AlertGeometryValue::PolygonGeometry(_)))
    ));
    assert_eq!(serde_json::to_value(value).unwrap()["geometry"], polygon());
}

#[test]
fn product_graph_retains_its_json_ld_wire_name() {
    let wire =
        json!({"@graph": [{"productCode": "AFD", "productName": "Area Forecast Discussion"}]});
    let collection: ProductTypeCollection = serde_json::from_value(wire.clone()).unwrap();
    assert_eq!(collection.at_graph[0].product_code, "AFD");
    assert_eq!(serde_json::to_value(collection).unwrap(), wire);
}

#[test]
fn transmitter_graph_and_identifiers_retain_json_ld_wire_names() {
    let recording: Value = serde_json::from_str(include_str!(
        "../../../spec/endpoints/zones/list_transmitters/examples/king_county.response.json"
    ))
    .unwrap();
    let wire = &recording["payload"];
    let collection: weather_gov::types::TransmitterCollection =
        serde_json::from_value(wire.clone()).unwrap();
    assert!(!collection.at_graph.is_empty());
    for (transmitter, original) in collection
        .at_graph
        .iter()
        .zip(wire["@graph"].as_array().unwrap())
    {
        assert_eq!(transmitter.at_id, original["@id"]);
    }
    let encoded = serde_json::to_value(collection).unwrap();
    assert_eq!(encoded["@graph"], wire["@graph"]);
    assert!(encoded.get("at_graph").is_none());
}
