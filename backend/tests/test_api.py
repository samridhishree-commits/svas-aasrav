from datetime import datetime, timezone
import math
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.errors import ServiceError
from backend.main import create_app
from backend.models import RouteRequest
from backend.providers import AirQualityProvider
from backend.sampling import sample_route, reduction_percent
from backend.service import RoutingService

def settings():
    return Settings(_env_file=None,neo4j_uri='',neo4j_password='')

class FakeMaps:
    def ensure_configured(self): pass
    def geocode(self,address):
        return {'lat':28.52 if 'Saket' in address else 28.71,'lng':77.2 if 'Saket' in address else 77.11,'name':address}
    def routes(self,*args):
        return [{'id':'route-0','duration_seconds':1800,'distance_meters':20000,'path':[{'lat':28.52,'lng':77.2},{'lat':28.71,'lng':77.11}],'description':'Standard','warnings':[]},
                {'id':'route-1','duration_seconds':2100,'distance_meters':22000,'path':[{'lat':28.52,'lng':77.2},{'lat':28.6,'lng':77.08},{'lat':28.71,'lng':77.11}],'description':'Alternative','warnings':[]}]

class FakeAir:
    def readings(self,points):
        return [{'aqi':150.0,'standard':'US','source':'Open-Meteo / CAMS','observed_at':datetime.now(timezone.utc).isoformat(),'grid_lat':28.6,'grid_lng':77.2} for p in points]

class FakeDatabase:
    def close(self): pass
    def ensure_available(self): pass
    def summary(self): return []
    def rank_routes(self,trip_id,routes,request):
        scores=[]
        for route in routes:
            weighted=sum(s['aqi']*s['seconds'] for s in route['samples'])
            seconds=sum(s['seconds'] for s in route['samples'])
            high=sum(s['seconds'] for s in route['samples'] if s['aqi']>200)
            scores.append({'id':route['id'],'average_aqi':weighted/seconds,'exposure_index':weighted/60,'high_aqi_seconds':high,
                'max_sampled_aqi':max(s['aqi'] for s in route['samples']),'routing_cost':seconds/60+weighted/6000,'eligible':seconds<=request.delivery_window_minutes*60 and (request.has_mask or high==0) and (request.max_aqi is None or max(s['aqi'] for s in route['samples'])<request.max_aqi),
                'sample_count':len(route['samples']),'observed_at':route['samples'][0]['observed_at']})
        return sorted(scores,key=lambda r:(not r['eligible'],r['routing_cost']))

@pytest.fixture
def client():
    with TestClient(create_app(settings(),maps=FakeMaps(),air=FakeAir(),database=FakeDatabase())) as test_client:
        yield test_client

def test_route_contract_and_same_winner(client):
    response=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini'})
    assert response.status_code==200
    result=response.json()
    assert result['ranking_engine']=='Neo4j Cypher'
    assert result['standard_route']==result['green_route']
    assert result['exposure_reduction_percent']==0
    assert result['lower_aqi_percent']==0
    assert result['graph']=={'candidate_routes':2,'samples':20,'air_zones':1}
    assert all(set(p)=={'lat','lng'} for p in result['standard_route'])

def test_validation_same_place_and_whitespace(client):
    assert client.post('/api/calculate-route',json={'pickup':'  ','drop':'Rohini'}).status_code==422
    assert client.post('/api/calculate-route',json={'pickup':'Saket','drop':' saket '}).status_code==422
    assert client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini','delivery_window_minutes':0}).status_code==422

def test_deadline_can_result_in_no_recommendation(client):
    response=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini','delivery_window_minutes':5})
    assert response.json()['recommended_route_id'] is None

def test_twenty_minute_deadline_explains_lateness_and_matching_aqi(client):
    result=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini','delivery_window_minutes':20}).json()
    assert result['deadline_summary']=={'requested_minutes':20,'fastest_minutes':30,'minimum_extra_minutes':10,'any_route_on_time':False}
    assert [r['late_by_minutes'] for r in result['routes']]==[10,15]
    assert all(not r['deadline_met'] and r['constraint_failures'] for r in result['routes'])
    assert result['recommended_route_id'] is None
    assert result['data_quality']['similar_route_averages'] is True
    assert all('best eligible' not in warning for warning in result['warnings'])

def test_exact_deadline_is_met_and_aqi_variation_is_preserved():
    class VariableAir(FakeAir):
        def readings(self,points):
            readings=super().readings(points)
            for index,reading in enumerate(readings):
                reading['aqi']=150 if index<10 else 100
            return readings
    service=RoutingService(settings(),FakeMaps(),VariableAir(),FakeDatabase())
    result=service.calculate(RouteRequest(pickup='Saket',drop='Rohini',delivery_window_minutes=30))
    assert result['deadline_summary']['any_route_on_time'] is True
    assert result['routes'][0]['late_by_minutes']==0
    assert result['routes'][1]['late_by_minutes']==5
    assert result['recommended_route_id']=='route-0' # Cleaner but late route must not win.
    assert result['data_quality']['similar_route_averages'] is False
    assert [r['average_aqi'] for r in result['routes']]==[150,100]

def test_cors_localhost_and_no_unknown_origin(client):
    good=client.options('/api/calculate-route',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST'})
    assert good.headers['access-control-allow-origin']=='http://localhost:5173'
    bad=client.options('/api/calculate-route',headers={'Origin':'https://unknown.example','Access-Control-Request-Method':'POST'})
    assert 'access-control-allow-origin' not in bad.headers

def test_city_aqi_is_provider_result_not_mock_constant(client):
    data=client.get('/api/city-aqi').json()
    assert data['aqi']==150 and data['standard']=='US'

def test_sampling_is_distance_based_and_preserves_time():
    path=[{'lat':28.5,'lng':77.1},{'lat':28.50001,'lng':77.1},{'lat':28.7,'lng':77.1}]
    samples=sample_route(path,1200,10)
    assert sum(p['seconds'] for p in samples)==1200
    assert samples[0]['lat']>28.505
    assert samples[-1]['lat']<28.7

def test_percentage_does_not_invent_savings():
    assert reduction_percent(100,120)==-20
    assert reduction_percent(100,100)==0
    assert reduction_percent(0,1) is None
    assert reduction_percent(0,0)==0

def test_upstream_failure_is_not_replaced_with_demo(client):
    class BrokenAir:
        def readings(self,points): raise ServiceError('AQI unavailable',502,'AQI_UNAVAILABLE')
    with TestClient(create_app(settings(),maps=FakeMaps(),air=BrokenAir(),database=FakeDatabase())) as test_client:
        response=test_client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini'})
        assert response.status_code==502
        assert response.json()['code']=='AQI_UNAVAILABLE'
        assert 'routes' not in response.json()

def test_open_meteo_batch_mapping_cache_and_nulls():
    calls=[]
    def respond(request):
        calls.append(request)
        entry={'latitude':28.6,'longitude':77.2,'current':{'time':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M'),'us_aqi':180,'pm2_5':32,'pm10':61}}
        return httpx.Response(200,json=[entry,entry])
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        air=AirQualityProvider(settings(),http)
        points=[{'lat':28.5,'lng':77.1},{'lat':28.7,'lng':77.2}]
        assert len(air.readings(points))==2
        air.readings(points)
        assert len(calls)==1
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'latitude':28.6,'longitude':77.2,'current':{'time':datetime.now(timezone.utc).isoformat(),'us_aqi':None}}))) as http:
        with pytest.raises(ServiceError): AirQualityProvider(settings(),http).readings([points[0]])

def test_missing_configuration_is_actionable():
    with TestClient(create_app(settings())) as client:
        response=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini'})
        assert response.status_code==503
        assert response.json()['code']=='NEO4J_NOT_CONFIGURED'

def test_fleet_suggestions_never_schedule_and_explanation_failure_preserves_routes():
    class FleetAI:
        def fleet(self,prompt):
            return {'status':'ready','rider_count':5,'deadline_assumed':True,
                'payload':RouteRequest(pickup='Saket',drop='Rohini',has_mask=False,max_aqi=301).model_dump()}
        def analyze(self,facts):raise ServiceError('Explanation unavailable',502,'AI_UNAVAILABLE')
    with TestClient(create_app(settings(),maps=FakeMaps(),air=FakeAir(),database=FakeDatabase(),gemini=FleetAI())) as client:
        result=client.post('/api/ai/fleet-suggestions',json={'prompt':'Five unmasked riders from Saket to Rohini'}).json()
        assert result['scheduled'] is False
        assert result['intent']['rider_count']==5
        assert result['comparison']['routes']
        assert result['story'] is None

def test_fleet_clarification_does_not_calculate_routes():
    class FleetAI:
        def fleet(self,prompt):return {'status':'needs_clarification','message':'How many riders?','payload':None}
    class NoMaps:
        def geocode(self,address):raise AssertionError('Must not route incomplete intent')
    with TestClient(create_app(settings(),maps=NoMaps(),air=FakeAir(),database=FakeDatabase(),gemini=FleetAI())) as client:
        result=client.post('/api/ai/fleet-suggestions',json={'prompt':'Some riders from Saket'}).json()
        assert result['status']=='needs_clarification'
