use weather_gov::types::OfficeHeadline;
fn headline_token(headline: &OfficeHeadline) -> &str {
    &headline.id2
}
fn main() { let _ = headline_token; }
