from datetime import datetime, timezone, timedelta
import httpx
import pytest
from backend.config import Settings
from backend.stations import StationAirQualityProvider
from backend.errors import ServiceError

def feed():
    return {'status':'ok','data':{'aqi':139,'idx':2554,
        'city':{'geo':[28.6341,77.2005],'name':'Mandir Marg'},
        'time':{'iso':datetime.now(timezone.utc).isoformat()},
        'attributions':[{'name':'CPCB','url':'https://cpcb.nic.in/'}]}}

def test_station_coordinates_provenance_and_no_cross_request_cache():
    calls=[]
    def respond(req):
        calls.append(req)
        return httpx.Response(200,json=feed())
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        air=StationAirQualityProvider(Settings(_env_file=None,waqi_api_token='test-token'),http)
        points=[{'lat':28.6139,'lng':77.209}]*2
        readings=air.readings(points)
        assert readings[0]['zone_id']=='waqi:2554'
        assert readings[0]['aqi']==139
        assert 2<readings[0]['station_distance_km']<3
        assert readings[0]['attributions'][0]['name']=='CPCB'
        assert len(calls)==1 # Only deduplicate within this request.
        air.readings(points)
        assert len(calls)==2

@pytest.mark.parametrize('kind,code',[('stale','STALE_AQI'),('distant','STATION_COVERAGE'),('null','WAQI_UNAVAILABLE'),('rejected','WAQI_ACCESS')])
def test_bad_station_data_is_not_substituted(kind,code):
    data=feed()
    if kind=='stale':data['data']['time']['iso']=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat()
    if kind=='distant':data['data']['city']['geo']=[29.5,77.2]
    if kind=='null':data['data']['aqi']='-'
    if kind=='rejected':data={'status':'error','data':'private-token'}
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as http:
        with pytest.raises(ServiceError) as exc:
            StationAirQualityProvider(Settings(_env_file=None,waqi_api_token='private-token'),http).readings([{'lat':28.6139,'lng':77.209}])
        assert exc.value.code==code
        assert 'private-token' not in exc.value.message
