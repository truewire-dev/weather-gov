from weather_gov.stations.list_stations import StationCollection
from weather_gov.stations.get_observations import ObservationCollection
from weather_gov.schemas import StationCollection as S2, ObservationCollection as O2, CollectionPagination, ObservationPagination

def f(a: StationCollection, b: ObservationCollection) -> tuple[S2, O2, CollectionPagination | None, ObservationPagination | None]:
    return a, b, a.get('pagination'), b.get('pagination')
