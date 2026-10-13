//! TRU-1316 review (#13 at 74dab54): live api.weather.gov through the generated Rust client.
//! Every product type's location map decodes (the `[]` empty-map fix), and two `type`
//! filters reach the service as one comma-separated item.
use std::collections::BTreeSet;
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::products::*;
use weather_gov::Weather;

#[tokio::test]
#[ignore]
async fn live_locations_for_every_type() {
    let c = Weather::with_options(CoreOptions::new("review@truewire.dev"));
    let o = CallOptions::default;
    let types = c.products.list_product_types(Default::default(), o()).await.unwrap();
    let (mut empty, mut full, mut bad) = (0, 0, Vec::new());
    for t in &types.graph {
        let req = list_locations_for_type::Request { type_id: t.product_code.clone(), ..Default::default() };
        match c.products.list_locations_for_type(req, o()).await {
            Ok(r) if r.locations.is_empty() => empty += 1,
            Ok(_) => full += 1,
            Err(e) => bad.push(format!("{}: {e}", t.product_code)),
        }
    }
    let all = c.products.list_locations(Default::default(), o()).await.unwrap();
    println!("types {} empty {empty} full {full} list_locations {}", types.graph.len(), all.locations.len());
    for b in &bad { println!("BAD {b}"); }
    assert!(bad.is_empty());
}

#[tokio::test]
#[ignore]
async fn live_two_types() {
    let c = Weather::with_options(CoreOptions::new("review@truewire.dev"));
    let req = list_products::Request { type_: Some(vec!["AFD".into(), "TOR".into()]), limit: Some(500), ..Default::default() };
    let p = c.products.list_products(req, CallOptions::default()).await.unwrap();
    let codes: BTreeSet<_> = p.graph.iter().map(|r| r.product_code.clone()).collect();
    println!("rows {} codes {codes:?}", p.graph.len());
    assert!(codes.contains("AFD"), "AFD missing: {codes:?}");
}
