import httpx
import pytest
from backend.config import Settings
from backend.openstreetmap import OpenStreetMapProvider
from backend.errors import ServiceError
from backend.models import RouteRequest
from pydantic import ValidationError


def feature(name, lng=77.21, lat=28.52, key='place', kind='district'):
    return {'type':'Feature','geometry':{'type':'Point','coordinates':[lng,lat]},
        'properties':{'name':name,'osm_key':key,'type':kind,'state':'Delhi'}}


def test_photon_axis_order_locality_preference_and_cache():
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'features':[
            feature('Saket',key='railway',kind='house'),feature('Saket',lng=77.2137,lat=28.5244)]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        maps=OpenStreetMapProvider(Settings(_env_file=None),http)
        result=maps.geocode('Saket, New Delhi')
        assert result['lat']==28.5244 and result['lng']==77.2137
        assert result['formatted_address']=='Saket, Delhi'
        assert calls[0].url.params['q']=='Saket'
        assert calls[0].headers['User-Agent'].startswith('svas-aasrav/')
        result['lat']=0
        assert maps.geocode('Saket, New Delhi')['lat']==28.5244
        assert len(calls)==1


@pytest.mark.parametrize('payload,code',[
    ({'features':[]},'LOCATION_NOT_FOUND'),
    ({'features':[feature('Mumbai',72.8,19.0)]},'OUTSIDE_SERVICE_AREA'),
    ({'features':[feature('Invalid',float('nan'),28.5)]},'INVALID_GEOCODING_RESPONSE'),
])
def test_photon_rejects_missing_and_invalid_locations(payload,code):
    # MockTransport JSON encoding rejects NaN, so use raw content for this case.
    import json
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=json.dumps(payload)))) as http:
        with pytest.raises(ServiceError) as exc:
            OpenStreetMapProvider(Settings(_env_file=None),http).geocode('test')
        assert exc.value.code==code


def test_osrm_routes_geojson_metrics_deduplication_and_cache():
    route={'duration':1800,'distance':25000,'geometry':{'type':'LineString','coordinates':[[77.2,28.52],[77.1,28.71]]},'legs':[{'summary':'Ring Road'}]}
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'code':'Ok','routes':[route,route]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        maps=OpenStreetMapProvider(Settings(_env_file=None),http)
        points=({'lat':28.52,'lng':77.2},{'lat':28.71,'lng':77.1})
        result=maps._route_options(list(points))
        assert len(result)==1 and result[0]['path'][0]==points[0]
        assert result[0]['duration_seconds']==1800
        assert result[0]['description']=='Ring Road'
        assert '77.2,28.52;77.1,28.71' in calls[0].url.path
        result[0]['path'][0]['lat']=0
        assert maps._route_options(list(points))[0]['path'][0]==points[0]
        assert len(calls)==1


def test_public_service_throttling_failure_is_actionable():
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(429))) as http:
        with pytest.raises(ServiceError) as exc:
            OpenStreetMapProvider(Settings(_env_file=None),http).geocode('Saket')
        assert exc.value.status_code==503 and exc.value.code=='MAPS_RATE_LIMITED'


def test_motorcycle_mode_is_not_misrepresented_as_osrm_driving():
    with pytest.raises(ValidationError):
        RouteRequest(pickup='Saket',drop='Rohini',travel_mode='TWO_WHEELER')

def test_corridor_expansion_returns_four_distinct_real_options(monkeypatch):
    maps=OpenStreetMapProvider(Settings(_env_file=None),None)
    origin={'lat':28.52,'lng':77.2}; destination={'lat':28.71,'lng':77.1}
    calls=[]
    def options(points,alternatives='3'):
        calls.append(points)
        return [{'id':'route-0','path':[{'lat':a['lat']+(b['lat']-a['lat'])*i/10,'lng':a['lng']+(b['lng']-a['lng'])*i/10} for a,b in zip(points,points[1:]) for i in range(11)],'duration_seconds':1800+len(calls)*60,
            'distance_meters':20000,'description':'Native','warnings':[]}]
    monkeypatch.setattr(maps,'_route_options',options)
    routes=maps.routes(origin,destination)
    assert len(routes)==4
    assert len({r['id'] for r in routes})==4
    assert sum(r.get('is_detour',False) for r in routes)==3
    assert all('detour' in r['description'] for r in routes[1:])

def test_failed_or_excessive_detours_preserve_native_route(monkeypatch):
    maps=OpenStreetMapProvider(Settings(_env_file=None),None)
    origin={'lat':28.52,'lng':77.2}; destination={'lat':28.71,'lng':77.1}
    def options(points,alternatives='3'):
        if len(points)==3:
            raise ServiceError('Unavailable',502,'MAPS_UNAVAILABLE')
        return [{'id':'route-0','path':points,'duration_seconds':1800,'distance_meters':20000,'description':'Native','warnings':[]}]
    monkeypatch.setattr(maps,'_route_options',options)
    routes=maps.routes(origin,destination)
    assert len(routes)==1 and routes[0]['warnings']
