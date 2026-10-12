use truewire_core::CallOptions;
use weather_gov::radar;
use weather_gov::Weather;

#[tokio::main]
async fn main() {
    let c = Weather::new("hello@truewire.dev");
    match c
        .radar
        .get_server(
            radar::get_server::Request::default(),
            CallOptions::default(),
        )
        .await
    {
        Ok(s) => println!("get_server(default) Ok: id {}", s.id2),
        Err(e) => println!(
            "get_server(default) Err: {}",
            e.to_string().chars().take(300).collect::<String>()
        ),
    }
    match c
        .radar
        .get_server_raw(
            radar::get_server::Request::default(),
            CallOptions::default(),
        )
        .await
    {
        Ok(v) => println!(
            "get_server_raw(default) Ok: keys {:?}, @graph len {:?}",
            v.as_object().map(|o| o.keys().cloned().collect::<Vec<_>>()),
            v["@graph"].as_array().map(Vec::len)
        ),
        Err(e) => println!("get_server_raw(default) Err: {e}"),
    }
    match c
        .radar
        .get_station(
            radar::get_station::Request::default(),
            CallOptions::default(),
        )
        .await
    {
        Ok(_) => println!("get_station(default) Ok"),
        Err(e) => println!(
            "get_station(default) Err: {}",
            e.to_string().chars().take(200).collect::<String>()
        ),
    }
}
