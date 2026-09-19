"""Sample equal-distance route intervals; allocate ETA proportionally to distance.

This is an AQI/time comparison proxy, not inhaled dose. Local speeds are unknown.
"""
import math
from .errors import ServiceError

def distance_m(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    delta_lat = lat2-lat1
    delta_lng = math.radians(b['lng']-a['lng'])
    h = math.sin(delta_lat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(delta_lng/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))

def sample_route(path, duration_seconds, count=10):
    if len(path) < 2 or duration_seconds <= 0:
        raise ServiceError('The routing provider returned an incomplete route.', code='INVALID_ROUTE')
    lengths = [distance_m(a,b) for a,b in zip(path,path[1:])]
    total = sum(lengths)
    if total < 1:
        raise ServiceError('Pickup and drop resolve to the same place.', 422, 'SAME_LOCATION')
    samples = []
    edge = 0
    walked = 0.0
    for index in range(count):
        target = total * (index + .5) / count
        while edge < len(lengths)-1 and walked + lengths[edge] < target:
            walked += lengths[edge]
            edge += 1
        fraction = min(1, max(0, (target-walked) / lengths[edge])) if lengths[edge] else 0
        a,b = path[edge],path[edge+1]
        samples.append({'lat':a['lat']+(b['lat']-a['lat'])*fraction,
                        'lng':a['lng']+(b['lng']-a['lng'])*fraction,
                        'seconds':duration_seconds/count, 'index':index})
    return samples

def reduction_percent(standard, candidate):
    # Negative is meaningful: the alternative has a higher estimate.
    if standard <= 0:
        return 0.0 if candidate == 0 else None
    return round((standard-candidate)/standard*100, 1)
