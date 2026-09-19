import json
from datetime import datetime, timezone
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.errors import ServiceError
from backend.gemini import GeminiProvider, TripFactsStore
from backend.main import create_app
from backend.models import ParseTripRequest
from backend.tests.test_api import FakeMaps, FakeAir, FakeDatabase


def settings():
    return Settings(_env_file=None,gemini_api_key='test-key',neo4j_uri='',neo4j_password='')


def extracted(**overrides):
    return {'pickup':'Saket','drop':'Rohini','delivery_window_minutes':60,'has_mask':False,
        'max_aqi':300,'clear_aqi_limit':False,'aqi_standard':'unspecified','unsupported_constraints':[], 'clarification':None,**overrides}


def generated(data):
    return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(data)}]}}]})


def test_parse_outputs_exact_valid_route_payload_and_uses_secret_header():
    calls=[]
    def respond(request):calls.append(request);return generated(extracted())
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        result=GeminiProvider(settings(),http).parse(ParseTripRequest(prompt='Saket to Rohini within an hour, AQI below 300. No mask.'))
    assert result['status']=='ready'
    assert result['payload']=={'pickup':'Saket','drop':'Rohini','delivery_window_minutes':60,'has_mask':False,
        'max_aqi':300,'aqi_standard':'US','travel_mode':'DRIVE'}
    assert calls[0].headers['x-goog-api-key']=='test-key'
    assert 'test-key' not in str(calls[0].url)
    config=json.loads(calls[0].content)['generationConfig']
    assert config['responseMimeType']=='application/json' and 'responseJsonSchema' in config


@pytest.mark.parametrize('overrides',[{'drop':None},{'aqi_standard':'IN'},
    {'unsupported_constraints':['avoid tolls']},{'pickup':'  '},{'drop':'saket'},
    {'clarification':'Which deadline did you intend?'}])
def test_ambiguous_or_unsupported_intent_never_produces_a_routable_payload(overrides):
    with httpx.Client(transport=httpx.MockTransport(lambda r:generated(extracted(**overrides)))) as http:
        result=GeminiProvider(settings(),http).parse(ParseTripRequest(prompt='Plan my trip'))
        assert result['status']=='needs_clarification' and result['payload'] is None


def test_omitted_preferences_preserve_form_and_explicit_remove_clears_limit():
    for clear,expected in [(False,250),(True,None)]:
        with httpx.Client(transport=httpx.MockTransport(lambda r:generated(extracted(delivery_window_minutes=None,has_mask=None,max_aqi=None,clear_aqi_limit=clear)))) as http:
            result=GeminiProvider(settings(),http).parse(ParseTripRequest(prompt='Saket to Rohini',delivery_window_minutes=85,has_mask=False,max_aqi=250))
            assert result['payload']['delivery_window_minutes']==85
            assert result['payload']['has_mask'] is False
            assert result['payload']['max_aqi']==expected


@pytest.mark.parametrize('status,code',[(429,'GEMINI_QUOTA'),(401,'GEMINI_AUTHENTICATION'),(403,'GEMINI_ACCESS'),(404,'GEMINI_MODEL_UNAVAILABLE')])
def test_gemini_provider_errors_are_sanitized(status,code):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'test-key private detail'}))) as http:
        with pytest.raises(ServiceError) as exc:GeminiProvider(settings(),http).parse(ParseTripRequest(prompt='Saket to Rohini'))
        assert exc.value.code==code and 'test-key' not in exc.value.message


def test_invalid_structured_output_is_rejected():
    with httpx.Client(transport=httpx.MockTransport(lambda r:generated(extracted(max_aqi='300',execute_cypher='anything')))) as http:
        with pytest.raises(ServiceError) as exc:GeminiProvider(settings(),http).parse(ParseTripRequest(prompt='Saket to Rohini'))
        assert exc.value.code=='GEMINI_INVALID_RESPONSE'


def test_analyst_uses_server_facts_and_cannot_accept_invented_metrics():
    class FakeGemini:
        calls=[]
        def analyze(self,facts):self.calls.append(facts);return {'source':'Gemini','facts':facts,'story':{'headline':'Test explanation'}}
    ai=FakeGemini()
    with TestClient(create_app(settings(),maps=FakeMaps(),air=FakeAir(),database=FakeDatabase(),gemini=ai)) as client:
        result=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini','max_aqi':150}).json()
        assert result['recommended_route_id'] is None  # strict below: exactly 150 fails
        assert all(r['max_sampled_aqi']==150 for r in result['routes'])
        body={'trip_id':result['trip_id'],'route_id':result['routes'][1]['id']}
        response=client.post('/api/ai/exposure-analysis',json=body)
        assert response.status_code==200
        facts=response.json()['facts']
        assert facts['any_route_eligible'] is False
        assert facts['average_aqi_verdict']=='unchanged'
        assert facts['exposure_verdict']=='higher' and facts['extra_minutes']==5
        assert client.post('/api/ai/exposure-analysis',json={**body,'aqi':1}).status_code==422
        assert client.post('/api/ai/exposure-analysis',json={**body,'route_id':'unrelated'}).status_code==422
        assert client.post('/api/ai/exposure-analysis',json={**body,'trip_id':'unknown'}).status_code==404
        assert len(ai.calls)==1
        allowed=client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini','max_aqi':151}).json()
        assert allowed['recommended_route_id'] is not None


def test_no_gemini_key_does_not_break_manual_routing():
    config=settings().model_copy(update={'gemini_api_key':''})
    with TestClient(create_app(config,maps=FakeMaps(),air=FakeAir(),database=FakeDatabase())) as client:
        response=client.post('/api/ai/parse-trip',json={'prompt':'Saket to Rohini'})
        assert response.status_code==503 and response.json()['code']=='GEMINI_NOT_CONFIGURED'
        assert client.post('/api/calculate-route',json={'pickup':'Saket','drop':'Rohini'}).status_code==200
        assert client.get('/api/health').json()['gemini_configured'] is False
