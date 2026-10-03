//! A listed headline's natural `id` works as the get_headline argument; `at_id` is its URL.
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

use truewire_core::serde_json::{self, Value};
use truewire_core::CallOptions;
use weather_gov::core::CoreOptions;
use weather_gov::{offices, Weather};

struct Mock(Child);

impl Drop for Mock {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn root() -> &'static Path {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
}

fn mock() -> (Mock, String) {
    let bin = std::env::var("TRUEWIRE_BIN")
        .map(PathBuf::from)
        .unwrap_or_else(|_| root().join(".venv/bin/truewire"));
    let child = Command::new(bin)
        .args(["mock", "--project"])
        .arg(root())
        .args(["--http-port", "0", "--ws-port", "0"])
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("start mock");
    let mut mock = Mock(child);
    let mut lines = BufReader::new(mock.0.stdout.take().expect("piped stdout")).lines();
    let url = lines
        .by_ref()
        .find_map(|line| {
            let line = line.expect("mock stdout");
            line.strip_prefix("HTTP ").map(|url| url.trim().to_owned())
        })
        .expect("mock HTTP URL");
    std::thread::spawn(move || lines.for_each(drop));
    (mock, url)
}

#[tokio::test]
async fn listed_headline_id_fetches_the_headline_and_at_id_remains_the_url() {
    let recorded: Value = serde_json::from_str(
        &std::fs::read_to_string(
            root().join("spec/endpoints/offices/get_headline/examples/wakefield.request.json"),
        )
        .expect("headline request recording"),
    )
    .expect("recorded JSON");
    let request = &recorded["request"];
    let office = request["office_id"].as_str().expect("office id");
    let id = request["headline_id"].as_str().expect("headline id");
    let (_mock, url) = mock();
    let client = Weather::with_options(CoreOptions::new("tests@truewire.dev").base_url(url));
    let list = client
        .offices
        .list_headlines(
            offices::list_headlines::Request::new(office.to_owned()),
            CallOptions::default(),
        )
        .await
        .expect("list headlines");
    let listed = list
        .at_graph
        .iter()
        .find(|h| h.id == id)
        .expect("listed id");
    assert_ne!(listed.id, listed.at_id);
    assert_eq!(
        listed.at_id,
        format!("{}/headlines/{}", listed.office, listed.id)
    );
    let headline = client
        .offices
        .get_headline(
            offices::get_headline::Request::new(office.to_owned(), listed.id.clone()),
            CallOptions::default(),
        )
        .await
        .expect("the natural headline.id lookup succeeds");
    assert_eq!(headline.id, listed.id);
    assert_eq!(headline.at_id, listed.at_id);
    assert_eq!(headline.title, listed.title);
    assert!(!headline.title.is_empty());
    let wire = serde_json::to_value(&headline).expect("serialize headline");
    assert_eq!(wire["id"], headline.id);
    assert_eq!(wire["@id"], headline.at_id);
    assert!(wire.get("at_id").is_none());
    println!(
        "PASS: headline.id={} fetches the headline; at_id={}",
        headline.id, headline.at_id
    );
}
