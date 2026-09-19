"""Keyless geocoding and routing, with bounded caches and polite public API use."""
from copy import deepcopy
import math
import re
import threading
import time
import httpx
from .errors import ServiceError
from .models import Coordinate


class OpenStreetMapProvider:
    def __init__(self, settings, http):
        self.settings, self.http = settings, http
        self.locks = {name: threading.Lock() for name in ('Photon', 'OSRM')}
        self.last_request = {'Photon': 0.0, 'OSRM': 0.0}
        self.cache = {'Photon': {}, 'OSRM': {}}

    def _get(self, provider, url, params, ttl):
        key = (url, tuple(sorted(params.items())))
        # Single-process server: serialize per provider, including concurrent users.
        with self.locks[provider]:
            now = time.monotonic()
            cached = self.cache[provider].get(key)
            if cached and now - cached[0] < ttl:
                return deepcopy(cached[1])
            delay = 1.05 - (now - self.last_request[provider])
            if delay > 0:
                time.sleep(delay)
            self.last_request[provider] = time.monotonic()
            try:
                response = self.http.get(url, params=params,
                    headers={'User-Agent': self.settings.maps_user_agent})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError('Expected object')
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 429:
                    raise ServiceError(f'{provider} is busy. Please wait a moment before trying again.', 503, 'MAPS_RATE_LIMITED') from None
                raise ServiceError(f'{provider} is temporarily unavailable. Please retry.', 502, f'{provider.upper()}_UNAVAILABLE') from None
            except (httpx.RequestError, ValueError):
                raise ServiceError(f'{provider} could not return data. Please retry.', 502, f'{provider.upper()}_UNAVAILABLE') from None
            if len(self.cache[provider]) >= 500:
                self.cache[provider].clear()
            self.cache[provider][key] = (time.monotonic(), payload)
            return deepcopy(payload)

    def geocode(self, address):
        # Delhi is already constrained by bbox. Removing a redundant city suffix
        # prevents Photon from prioritizing hotels named "New Delhi Saket".
        query = re.sub(r',\s*(?:new delhi|delhi(?: ncr)?)(?:,\s*india)?\s*$', '', address, flags=re.I).strip() or address
        payload = self._get('Photon', self.settings.photon_base_url.rstrip('/') + '/api/', {
            'q': query, 'lat': 28.6139, 'lon': 77.209,
            'bbox': '76.8,28.35,77.65,28.95', 'limit': 8, 'lang': 'en',
        }, 86400)
        try:
            features = payload['features']
            if not features:
                raise ServiceError(f'Could not locate "{address}". Try the locality, street or landmark in Delhi NCR.', 422, 'LOCATION_NOT_FOUND')
            # An exact locality name should resolve to the locality, not its metro stop.
            def relevance(feature):
                props = feature.get('properties', {})
                exact = props.get('name', '').casefold() == query.casefold()
                place = props.get('osm_key') == 'place'
                district = props.get('type') in ('district', 'locality', 'city')
                return (exact and place, exact and district, exact)
            feature = max(features, key=relevance)
            if feature['geometry']['type'] != 'Point':
                raise ValueError('Expected point')
            lng, lat = feature['geometry']['coordinates'][:2]
            point = Coordinate(lat=lat, lng=lng).model_dump()
            if not (28.35 <= point['lat'] <= 28.95 and 76.8 <= point['lng'] <= 77.65):
                raise ServiceError('This planner currently supports Delhi NCR locations only.', 422, 'OUTSIDE_SERVICE_AREA')
            props = feature['properties']
            parts = list(dict.fromkeys(str(props[k]) for k in ('name', 'street', 'district', 'city', 'county', 'state', 'postcode') if props.get(k)))
            return {**point, 'name': address, 'formatted_address': ', '.join(parts) or address,
                    'source': 'Photon / OpenStreetMap'}
        except ServiceError:
            raise
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            raise ServiceError('Address search returned an invalid location. Try a more specific address.', 502, 'INVALID_GEOCODING_RESPONSE') from None

    def _route_options(self, points, alternatives='3'):
        coordinates=';'.join(f"{p['lng']},{p['lat']}" for p in points)
        payload=self._get('OSRM',f'{self.settings.osrm_base_url.rstrip("/")}/route/v1/driving/{coordinates}',{
            'alternatives':alternatives,'geometries':'geojson','overview':'full',
            'steps':'false','radiuses':';'.join('1000' for p in points),'continue_straight':'true',
        },300)
        return self._decode_routes(payload)

    @staticmethod
    def _distinct(candidate,routes):
        cells=lambda route:{(round(p['lat'],3),round(p['lng'],3)) for p in route['path']}
        new=cells(candidate)
        for route in routes:
            old=cells(route)
            if len(new&old)/max(1,min(len(new),len(old)))>0.88:
                return False
        return True

    def routes(self, origin, destination, travel_mode='DRIVE'):
        if travel_mode != 'DRIVE':
            raise ServiceError('This OSRM server supports driving routes only.', 422, 'UNSUPPORTED_TRAVEL_MODE')
        routes=self._route_options([origin,destination])
        fastest=min(r['duration_seconds'] for r in routes)
        # Ask for real, road-following detours when native alternatives are sparse.
        # These are explicitly labelled; never fabricate a third polyline.
        lat_scale=111.32
        lng_scale=lat_scale*math.cos(math.radians((origin['lat']+destination['lat'])/2))
        dx=(destination['lng']-origin['lng'])*lng_scale
        dy=(destination['lat']-origin['lat'])*lat_scale
        length=math.hypot(dx,dy)
        if length>=3:
            offset=min(6,max(1.5,length*.18))
            for fraction,side in [(0.5,1),(0.5,-1),(0.35,1),(0.65,-1)]:
                if len(routes)>=self.settings.route_target_count:break
                x=-dy/length*offset*side
                y=dx/length*offset*side
                via={'lat':origin['lat']+(destination['lat']-origin['lat'])*fraction+y/lat_scale,
                     'lng':origin['lng']+(destination['lng']-origin['lng'])*fraction+x/lng_scale}
                if not (28.35<=via['lat']<=28.95 and 76.8<=via['lng']<=77.65):continue
                direction=('east' if x>0 else 'west') if abs(x)>=abs(y) else ('north' if y>0 else 'south')
                try:
                    options=self._route_options([origin,via,destination],'false')
                except ServiceError as error:
                    if error.code=='MAPS_RATE_LIMITED':break
                    continue  # Optional detours must not erase valid direct routes.
                for route in options:
                    if route['duration_seconds']>fastest*1.65 or not self._distinct(route,routes):continue
                    route.update(description=f'Via {direction} corridor (detour)',is_detour=True,via=via)
                    routes.append(route)
                    break
        routes=sorted(routes,key=lambda r:r['duration_seconds'])[:self.settings.route_target_count]
        for index,route in enumerate(routes):route['id']=f'route-{index}'
        if len(routes)<self.settings.route_target_count:
            routes[0]['warnings'].append(f'Found {len(routes)} distinct road routes. Additional corridors did not yield a sufficiently different, reasonable detour.')
        return routes

    def _decode_routes(self,payload):
        if payload.get('code') in ('NoRoute', 'NoSegment'):
            raise ServiceError('No driving route connects these locations. Try a nearby street or landmark.', 404, 'NO_ROUTE')
        try:
            if payload.get('code') != 'Ok':
                raise ValueError('OSRM rejected request')
            routes, seen = [], set()
            for raw in payload['routes'][:4]:
                duration, distance = float(raw['duration']), float(raw['distance'])
                if not math.isfinite(duration) or duration <= 0 or not math.isfinite(distance) or distance <= 0:
                    raise ValueError('Invalid metrics')
                if raw['geometry']['type'] != 'LineString':
                    raise ValueError('Expected line')
                path = [Coordinate(lat=p[1], lng=p[0]).model_dump() for p in raw['geometry']['coordinates']]
                if len(path) < 2:
                    raise ValueError('Incomplete geometry')
                signature = tuple((p['lat'], p['lng']) for p in path)
                if signature in seen:
                    continue
                seen.add(signature)
                summary = ' / '.join(leg.get('summary', '') for leg in raw.get('legs', []) if leg.get('summary'))
                routes.append({'id': f'route-{len(routes)}', 'path': path, 'duration_seconds': duration,
                    'distance_meters': distance, 'description': summary or f'OSRM driving option {len(routes) + 1}',
                    'warnings': []})
            if not routes:
                raise ServiceError('No driving route was returned for these locations.', 404, 'NO_ROUTE')
            return routes
        except ServiceError:
            raise
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            raise ServiceError('OSRM returned no usable route. Please retry.', 502, 'INVALID_ROUTES_RESPONSE') from None
