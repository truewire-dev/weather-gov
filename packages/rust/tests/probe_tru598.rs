//! TRU-598 reproduction (TRU-534 on OfficeHeadline): `h.id` is the URL, `h.id2` the id `get_headline` takes.
//! Run: TRUEWIRE_BIN=<venv>/bin/truewire cargo test --test probe_tru598 -- --nocapture
use std::io::{BufRead, BufReader};
use std::process::{Command, Stdio};
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::Weather;

fn mock() -> (std::process::Child, String) {
    let root = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
    let mut child = Command::new(std::env::var("TRUEWIRE_BIN").unwrap())
        .args(["mock", "--project", root, "--http-port", "0", "--ws-port", "0"])
        .stdout(Stdio::piped()).stderr(Stdio::null()).spawn().unwrap();
    let mut lines = BufReader::new(child.stdout.take().unwrap()).lines();
    let url = lines.by_ref().find_map(|l| {
        let l = l.unwrap();
        l.strip_prefix("HTTP").map(|u| u.trim().to_string())
    }).unwrap();
    std::thread::spawn(move || lines.for_each(drop));
    (child, url)
}

/// A user lists headlines and fetches one by the field named `id`.
#[tokio::test]
async fn headline_id_is_the_url_not_the_id_get_headline_takes() {
    let (mut child, url) = mock();
    let client = Weather::with_options(CoreOptions::new("probe@truewire.dev").base_url(url));
    let list = client.offices.list_headlines(
        weather_gov::offices::list_headlines::Request { office_id: "AKQ".into(), ..Default::default() },
        CallOptions::default()).await.unwrap();
    let first = list.graph.iter().find(|h| h.id2 == "8c67c3a1e638b30d1d9dd1524ab53330").unwrap();
    println!("headline.id  = {}", first.id);
    println!("headline.id2 = {}", first.id2);
    let natural = client.offices.get_headline(
        weather_gov::offices::get_headline::Request {
            office_id: "AKQ".into(), headline_id: first.id.clone(), ..Default::default() },
        CallOptions::default()).await;
    println!("get_headline(headline_id: h.id)  -> {:?}", natural.as_ref().map(|h| &h.title));
    let right = client.offices.get_headline(
        weather_gov::offices::get_headline::Request {
            office_id: "AKQ".into(), headline_id: first.id2.clone(), ..Default::default() },
        CallOptions::default()).await;
    println!("get_headline(headline_id: h.id2) -> {:?}", right.as_ref().map(|h| &h.title));
    let _ = child.kill();
    assert!(natural.is_err());
    assert!(right.is_ok());
}
