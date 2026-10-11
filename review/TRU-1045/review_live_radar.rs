//! TRU-1045 review (#18/#20): decode live api.weather.gov radar answers through the generated types.
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::radar::*;
use weather_gov::Weather;

#[tokio::test]
#[ignore]
async fn live_radar_sweep() {
    let c = Weather::with_options(CoreOptions::new("review@truewire.dev"));
    let o = CallOptions::default;
    let mut bad = Vec::new();
    let raw = c.radar.list_stations_raw(list_stations::Request::default(), o()).await.unwrap();
    let ids: Vec<String> = raw["features"].as_array().unwrap().iter()
        .map(|f| f["properties"]["id"].as_str().unwrap().to_string()).collect();
    println!("stations: {}", ids.len());
    if let Err(e) = c.radar.list_stations(list_stations::Request::default(), o()).await {
        bad.push(format!("list_stations(all): {e}"));
    }
    for st in ["WSR-88D", "TDWR", "Profiler"] {
        if let Err(e) = c.radar.list_stations(list_stations::Request { station_type: Some(vec![st.into()]), ..Default::default() }, o()).await {
            bad.push(format!("list_stations({st}): {e}"));
        }
    }
    for id in ids.iter().step_by(4) {
        if let Err(e) = c.radar.get_station(get_station::Request { station_id: id.clone(), ..Default::default() }, o()).await {
            bad.push(format!("get_station({id}): {e}"));
        }
        if let Err(e) = c.radar.list_station_alarms(list_station_alarms::Request { station_id: id.clone(), ..Default::default() }, o()).await {
            bad.push(format!("list_station_alarms({id}): {e}"));
        }
    }
    let servers = c.radar.list_servers_raw(list_servers::Request::default(), o()).await.unwrap();
    if let Err(e) = c.radar.list_servers(list_servers::Request::default(), o()).await {
        bad.push(format!("list_servers: {e}"));
    }
    for s in servers["@graph"].as_array().unwrap() {
        let id = s["id"].as_str().unwrap().to_string();
        if let Err(e) = c.radar.get_server(get_server::Request { server_id: id.clone(), ..Default::default() }, o()).await {
            bad.push(format!("get_server({id}): {e}"));
        }
    }
    if let Err(e) = c.radar.list_spgds(list_spgds::Request::default(), o()).await {
        bad.push(format!("list_spgds: {e}"));
    }
    for host in [get_queue::RequestHost::Rds, get_queue::RequestHost::Tds] {
        // No Default on this Request (required enum): every field spelled out.
        let r = get_queue::Request { host, limit: Some(2000), arrived: None, created: None, published: None, station: None, type_: None, feed: None, resolution: None, extra: Default::default() };
        if let Err(e) = c.radar.get_queue(r, o()).await {
            bad.push(format!("get_queue({host:?}): {e}"));
        }
    }
    for b in &bad { println!("BAD {b}"); }
    assert!(bad.is_empty(), "{} failures", bad.len());
}
