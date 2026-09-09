//! Hand-written core for the weather.gov client: the transport, the `User-Agent` the
//! service asks for, the envelope, and the RFC 7807 error mapping.
//!
//! Every generated struct holds its core as an `Arc<dyn HttpEndpoint<DefaultMeta>>` from
//! `truewire_core` and calls `request` on it; this is the one place that knows how to
//! reach the service. Nothing here is generated, and regenerating never touches it.
//!
//! There are no credentials. The National Weather Service answers every endpoint here to
//! anyone who identifies themselves in `User-Agent`, which is why `contact` is a required
//! field of `CoreOptions` rather than an `Option`: a default would be a lie about who is
//! calling.

use async_trait::async_trait;
use truewire_core::http::{RequestOptions, Response};
use truewire_core::serde_json::Value;
use truewire_core::{Error, HttpCall, HttpClient, HttpEndpoint, Result};

use crate::meta::DefaultMeta;

/// The one host. There is no staging environment and no versioned prefix: the API is
/// versioned through the `Accept` header instead.
pub const API: &str = "https://api.weather.gov";

/// What most of this API answers in. The service also serves `application/ld+json` and
/// `application/vnd.noaa.dwml+xml` from the same paths, so asking matters -- and asking
/// for `application/geo+json` is what pins the response shapes these types describe.
pub const GEO_JSON: &str = "application/geo+json";

/// What `Core::new` takes.
#[derive(Debug, Clone)]
pub struct CoreOptions {
    /// How the service can reach you -- an email address or a project URL. Sent in
    /// `User-Agent` on every call. Not optional: there is no API key, and this is the
    /// whole of identifying yourself.
    pub contact: String,
    /// The host to call. The live API by default; a `truewire mock` address in tests.
    pub base_url: Option<String>,
    /// The HTTP client to send through; one is made when omitted.
    pub http: Option<HttpClient>,
}

impl CoreOptions {
    /// The options with nothing but a contact, which is the common case.
    pub fn new(contact: impl Into<String>) -> Self {
        Self { contact: contact.into(), base_url: None, http: None }
    }

    /// Point the client at another host -- a `truewire mock` address in tests.
    pub fn base_url(mut self, base_url: impl Into<String>) -> Self {
        self.base_url = Some(base_url.into());
        self
    }
}

/// The transport every endpoint group calls.
#[derive(Debug)]
pub struct Core {
    base_url: String,
    contact: String,
    http: HttpClient,
}

impl Core {
    pub fn new(options: CoreOptions) -> Self {
        let base_url = options.base_url.unwrap_or_else(|| API.to_string());
        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            contact: options.contact,
            http: options.http.unwrap_or_default(),
        }
    }

    /// Headers for one call. The same on every call: there is nothing per-endpoint.
    fn headers(&self) -> Vec<(String, String)> {
        vec![
            ("Accept".to_string(), GEO_JSON.to_string()),
            ("User-Agent".to_string(), user_agent(&self.contact)),
        ]
    }
}

/// The `User-Agent` the service asks for: who is calling, and how to reach them.
///
/// The published guidance is a string identifying the application with contact
/// information, and a caller that sends nothing useful can be blocked.
pub fn user_agent(contact: &str) -> String {
    format!("truewire-weather-gov ({contact})")
}

#[async_trait]
impl HttpEndpoint<DefaultMeta> for Core {
    /// Send one request, unwrap the declared envelope, and return what is left.
    ///
    /// Every endpoint here is a `GET` whose parameters travel in the query string. The
    /// order matters: the generated type describes the unwrapped value, not the wire
    /// frame the spec's response schema describes.
    async fn request(&self, call: HttpCall<'_, DefaultMeta>) -> Result<Value> {
        let mut path = call.path.to_string();
        let mut query: Vec<(String, Option<String>)> = Vec::new();
        if let Some(Value::Object(fields)) = call.request {
            for (name, value) in fields {
                let placeholder = format!("{{{name}}}");
                if path.contains(&placeholder) {
                    path = path.replace(&placeholder, &encode_path_value(&plain(&value)));
                    continue;
                }
                // A list-valued filter (`state`, `severity`) travels as repeated keys,
                // which is what the service reads and what `truewire mock` matches. The
                // runtime's `query_from` would send the array as one JSON string.
                match value {
                    Value::Null => {}
                    Value::Array(items) => {
                        for item in items {
                            query.push((name.clone(), Some(plain(&item))));
                        }
                    }
                    other => query.push((name, Some(plain(&other)))),
                }
            }
        }
        let method = call.method.unwrap_or("GET").to_uppercase();
        let url = format!("{}/{}", self.base_url, path.trim_start_matches('/'));
        let mut options = RequestOptions::new().headers(self.headers()).query(query);
        if let Some(timeout) = call.options.timeout {
            options = options.timeout(timeout);
        }
        let response = self.http.request(&method, &url, options).await?;
        if response.status >= 400 {
            return Err(map_error(&method, &path, &response));
        }
        unwrap(response.json()?, call.meta.payload.as_deref())
    }
}

/// A dumped value as query or path text: a string as it is, anything else as JSON.
fn plain(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        other => other.to_string(),
    }
}

/// Percent-encode a path value, keeping the `:` an alert identifier is built from.
///
/// `:` is a legal path character (RFC 3986 `pchar`), an alert id is `urn:oid:...`, and the
/// service publishes that id inside the URL it hands back -- so encoding it would send a
/// URL the API never printed. Everything outside the unreserved set is encoded, `/`
/// included: no path parameter here is a path fragment, so a `/` in one would be an
/// injected path segment.
fn encode_path_value(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' | b':' => {
                out.push(byte as char)
            }
            other => out.push_str(&format!("%{other:02X}")),
        }
    }
    out
}

/// Read the declared envelope payload off a decoded response body.
///
/// `payload` is the dotted path an endpoint declared, `None` for one that declares no
/// envelope. An endpoint that declares one and does not get it is a wire change, not a
/// missing optional field, so it is an error here rather than a deserialization failure a
/// frame later.
fn unwrap(raw: Value, payload: Option<&str>) -> Result<Value> {
    let Some(payload) = payload else { return Ok(raw) };
    let mut value = raw;
    for key in payload.split('.') {
        value = match value {
            Value::Object(mut fields) => fields.remove(key).ok_or_else(|| {
                Error::api(format!(
                    "response has no `{payload}` to unwrap; the wire shape has changed"
                ))
            })?,
            _ => {
                return Err(Error::api(format!(
                    "response has no `{payload}` to unwrap; the wire shape has changed"
                )))
            }
        };
    }
    Ok(value)
}

/// Map a non-2xx answer onto the runtime's errors.
///
/// The service answers errors in RFC 7807 problem detail, and a bad parameter adds a
/// `parameterErrors` list naming exactly which one and why. That list is the most useful
/// thing in the body, so it is what the message leads with when it is there.
fn map_error(method: &str, path: &str, response: &Response) -> Error {
    let text = response.text();
    let body = response
        .json()
        .unwrap_or_else(|_| Value::String(text.clone()));
    let problems = body.get("parameterErrors").and_then(Value::as_array);
    let detail = match problems {
        Some(items) if !items.is_empty() => items
            .iter()
            .map(|item| {
                let parameter = item.get("parameter").and_then(Value::as_str).unwrap_or("?");
                let message = item.get("message").and_then(Value::as_str).unwrap_or("");
                format!("{parameter}: {message}")
            })
            .collect::<Vec<_>>()
            .join("; "),
        _ => match (
            body.get("detail").and_then(Value::as_str),
            body.get("title").and_then(Value::as_str),
        ) {
            (Some(detail), _) => detail.to_string(),
            (None, Some(title)) => title.to_string(),
            _ => text.chars().take(300).collect(),
        },
    };
    let message = format!("{method} {path}: HTTP {}: {detail}", response.status);
    let error = match response.status {
        400 => Error::bad_request(message),
        429 => Error::rate_limited(message),
        _ => Error::api(message),
    };
    error.with_status(response.status).with_body(body)
}
