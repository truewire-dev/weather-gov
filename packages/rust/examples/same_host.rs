use weather_gov::radar::get_queue::{RadarQueue, RequestHost};
fn from_host(queue: &RadarQueue, asked: RequestHost) -> usize {
    queue.graph.iter().filter(|p| p.host == asked).count()
}
fn main() {
    let _ = from_host;
}
