//! TRU-1045 review (#13): decode live api.weather.gov product answers through the generated types.
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::products::*;
use weather_gov::Weather;

#[tokio::test]
#[ignore]
async fn live_products_sweep() {
    let c = Weather::with_options(CoreOptions::new("review@truewire.dev"));
    let o = CallOptions::default;
    let mut bad = Vec::new();
    let types = c.products.list_product_types(Default::default(), o()).await.unwrap();
    let locs = c.products.list_locations(Default::default(), o()).await.unwrap();
    println!("types {} locations {}", types.graph.len(), locs.locations.len());
    for t in ["AFD", "TOR", "CF6", "ZFP", "HWO"] {
        match c.products.list_products(list_products::Request { type_: Some(vec![t.into()]), limit: Some(500), ..Default::default() }, o()).await {
            Ok(p) => println!("{t}: {}", p.graph.len()),
            Err(e) => bad.push(format!("list_products({t}): {e}")),
        }
        if let Err(e) = c.products.list_products_by_type(list_products_by_type::Request { type_id: t.into(), ..Default::default() }, o()).await {
            bad.push(format!("list_products_by_type({t}): {e}"));
        }
        if let Err(e) = c.products.list_locations_for_type(list_locations_for_type::Request { type_id: t.into(), ..Default::default() }, o()).await {
            bad.push(format!("list_locations_for_type({t}): {e}"));
        }
    }
    match c.products.list_products(list_products::Request { limit: Some(500), ..Default::default() }, o()).await {
        Ok(p) => {
            for row in p.graph.iter().step_by(25) {
                if let Err(e) = c.products.get_product(get_product::Request { product_id: row.id2.clone(), ..Default::default() }, o()).await {
                    bad.push(format!("get_product({} {}): {e}", row.product_code, row.id2));
                }
            }
        }
        Err(e) => bad.push(format!("list_products(all): {e}")),
    }
    for l in ["SEW", "OKX", "LOX", "BOU"] {
        if let Err(e) = c.products.list_types_for_location(list_types_for_location::Request { location_id: l.into(), ..Default::default() }, o()).await {
            bad.push(format!("list_types_for_location({l}): {e}"));
        }
        if let Err(e) = c.products.list_products_by_type_and_location(list_products_by_type_and_location::Request { type_id: "AFD".into(), location_id: l.into(), ..Default::default() }, o()).await {
            bad.push(format!("by_type_and_location({l}): {e}"));
        }
        if let Err(e) = c.products.get_latest_product(get_latest_product::Request { type_id: "AFD".into(), location_id: l.into(), ..Default::default() }, o()).await {
            bad.push(format!("get_latest_product({l}): {e}"));
        }
    }
    for b in &bad { println!("BAD {b}"); }
    assert!(bad.is_empty(), "{} failures", bad.len());
}
