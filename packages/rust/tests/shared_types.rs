use truewire_core::serde_json::{self, json, Value};
// truewire 0.11 inlines the geometries per feature (`ZoneFeatureGeometry`,
// `AlertFeatureGeometry`) and names the JSON-LD fields `id`/`id2`, `graph`. The shared
// `ZoneGeometry`/`AlertGeometry`/`ZoneKind` types and the `at_*` names return after the
// next release (TRU-1046); these tests pin the wire behaviour, which 0.11 already keeps.
use weather_gov::types::{
    AlertFeature, AlertFeatureGeometry, ProductTypeCollection, Zone, ZoneFeature,
    ZoneFeatureGeometry, ZoneType2,
};

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
fn zone_geometry_and_kind_round_trip() {
    let zone: Zone = serde_json::from_value(zone_wire()).unwrap();
    assert_eq!(zone.type_2, ZoneType2::Public);
    let wire = serde_json::to_value(&zone).unwrap();
    assert_eq!(wire["type"], "public");
    assert_eq!(wire["@type"], "wx:Zone");
    assert_eq!(wire["id"], "WAZ558");
    assert_eq!(wire["@id"], zone.id);
    assert!(wire.get("type_").is_none());

    let mut wire = json!({"id": zone.id, "type": "Feature", "properties": zone_wire(),
        "geometry": null});
    let feature: ZoneFeature = serde_json::from_value(wire.clone()).unwrap();
    assert!(feature.geometry.is_none());
    assert!(serde_json::to_value(feature).unwrap()["geometry"].is_null());
    wire["geometry"] = polygon();
    let feature: ZoneFeature = serde_json::from_value(wire.clone()).unwrap();
    assert!(feature.geometry.is_some());
    assert!(matches!(
        feature.geometry,
        Some(ZoneFeatureGeometry::PolygonGeometry(_))
    ));
    assert_eq!(
        serde_json::to_value(feature).unwrap()["geometry"],
        polygon()
    );
}

#[test]
#[ignore = "TRU-760: truewire 0.11 emits required-nullable fields as plain Option, so serde accepts them missing"]
fn zone_feature_requires_geometry() {
    let zone: Zone = serde_json::from_value(zone_wire()).unwrap();
    let wire = json!({"id": zone.id, "type": "Feature", "properties": zone_wire()});
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
    let geometry: &Option<Option<AlertFeatureGeometry>> = &missing.geometry;
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
        Some(Some(AlertFeatureGeometry::PolygonGeometry(_)))
    ));
    assert_eq!(serde_json::to_value(value).unwrap()["geometry"], polygon());
}

#[test]
fn product_graph_retains_its_json_ld_wire_name() {
    let wire =
        json!({"@graph": [{"productCode": "AFD", "productName": "Area Forecast Discussion"}]});
    let collection: ProductTypeCollection = serde_json::from_value(wire.clone()).unwrap();
    assert_eq!(collection.graph[0].product_code, "AFD");
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
    assert!(!collection.graph.is_empty());
    for (transmitter, original) in collection
        .graph
        .iter()
        .zip(wire["@graph"].as_array().unwrap())
    {
        assert_eq!(transmitter.id, original["@id"]);
    }
    let encoded = serde_json::to_value(collection).unwrap();
    assert_eq!(encoded["@graph"], wire["@graph"]);
    assert!(encoded.get("at_graph").is_none());
}
