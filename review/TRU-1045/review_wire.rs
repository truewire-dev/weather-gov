//! TRU-1045 review: the exact query the #15 core puts on the wire.
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::mpsc;
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::Weather;

fn capture(n: usize) -> (String, mpsc::Receiver<String>) {
    let l = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}", l.local_addr().unwrap());
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        for s in l.incoming().take(n) {
            let mut s = s.unwrap();
            let mut line = String::new();
            BufReader::new(&s).read_line(&mut line).unwrap();
            tx.send(line.split_whitespace().nth(1).unwrap().to_string()).unwrap();
            let body = r#"{"type":"FeatureCollection","features":[]}"#;
            write!(s, "HTTP/1.1 200 OK\r\ncontent-type: application/geo+json\r\ncontent-length: {}\r\nconnection: close\r\n\r\n{body}", body.len()).unwrap();
        }
    });
    (url, rx)
}

#[tokio::test]
async fn wire_forms() {
    let (url, rx) = capture(4);
    let c = Weather::with_options(CoreOptions::new("review@truewire.dev").base_url(url));
    use weather_gov::stations::list_stations::Request;
    for r in [
        Request { id: Some(vec!["KSEA".into(), "KPDX".into()]), ..Default::default() },
        Request { id: Some(vec!["KSEA,KPDX".into()]), ..Default::default() },
        Request { id: Some(vec![]), ..Default::default() },
        Request { state: Some(vec!["WA".into(), "OR".into()]), limit: Some(2), ..Default::default() },
    ] {
        let _ = c.stations.list_stations_raw(r, CallOptions::default()).await;
        println!("WIRE {}", rx.recv().unwrap());
    }
}
