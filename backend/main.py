from contextlib import asynccontextmanager
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import Settings
from .database import Database
from .errors import ServiceError
from .models import RouteRequest, ParseTripRequest, AnalyzeTripRequest, FleetSuggestionRequest
from .gemini import GeminiProvider, TripFactsStore
from .providers import AirQualityProvider
from .stations import StationAirQualityProvider
from .openstreetmap import OpenStreetMapProvider
from .service import RoutingService

def create_app(settings=None, *, maps=None, air=None, database=None, gemini=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        with httpx.Client(timeout=httpx.Timeout(25,connect=10)) as http:
            db = database or Database(settings)
            app.state.db = db
            app.state.maps = maps or OpenStreetMapProvider(settings,http)
            app.state.air = air or (StationAirQualityProvider(settings,http) if settings.waqi_api_token else AirQualityProvider(settings,http))
            app.state.routing = RoutingService(settings,app.state.maps,app.state.air,db)
            app.state.gemini = gemini or GeminiProvider(settings,http)
            app.state.trip_facts = TripFactsStore()
            try:
                yield
            finally:
                db.close()
    app = FastAPI(title='svas-aasrav API',version='1.0.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
        allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    @app.exception_handler(ServiceError)
    async def service_error(request, error):
        return JSONResponse(status_code=error.status_code,content={'detail':error.message,'code':error.code})

    @app.exception_handler(Exception)
    async def unexpected_error(request,error):
        # Do not log provider URLs, payloads or exception messages that may contain credentials.
        logging.getLogger('svas').error('Unhandled API error: %s',type(error).__name__)
        return JSONResponse(status_code=500,content={'detail':'The request could not be completed. Please retry.','code':'INTERNAL_ERROR'})

    @app.get('/api/health')
    def health():
        return {'status':'ok','service':'svas-aasrav','maps_provider':'OpenStreetMap / OSRM',
            'geocoding_provider':'Photon','map_api_key_required':False,
            'gemini_configured':bool(settings.gemini_api_key),
            'aqi_provider':'WAQI stations' if settings.waqi_api_token else 'Open-Meteo / CAMS',
            'neo4j_configured':bool(settings.neo4j_uri and settings.neo4j_password)}

    @app.get('/api/city-aqi')
    def city_aqi(request:Request):
        reading = request.app.state.air.readings([{'lat':28.6139,'lng':77.2090}])[0]
        return {'city':'Delhi','model_resolution_km':None if reading.get('station_name') else 45,'data_type':'model_estimate',**reading}

    @app.post('/api/calculate-route')
    def calculate_route(body:RouteRequest,request:Request):
        result=request.app.state.routing.calculate(body)
        request.app.state.trip_facts.put(result)
        return result

    @app.post('/api/ai/parse-trip')
    def parse_trip(body:ParseTripRequest,request:Request):
        return request.app.state.gemini.parse(body)

    @app.post('/api/ai/exposure-analysis')
    def exposure_analysis(body:AnalyzeTripRequest,request:Request):
        facts=request.app.state.trip_facts.facts(body.trip_id,body.route_id)
        return request.app.state.gemini.analyze(facts)

    @app.post('/api/ai/fleet-suggestions')
    def fleet_suggestions(body:FleetSuggestionRequest,request:Request):
        intent=request.app.state.gemini.fleet(body.prompt)
        if intent['status']!='ready':return intent
        result=request.app.state.routing.calculate(RouteRequest(**intent['payload']),rider_count=intent['rider_count'])
        request.app.state.trip_facts.put(result)
        facts=request.app.state.trip_facts.facts(result['trip_id'],result['recommended_route_id'] or result['green_route_id'])
        story=None
        try:
            story=request.app.state.gemini.analyze(facts)['story']
        except ServiceError:
            pass # The computed suggestions remain useful if explanation generation fails.
        return {'status':'ready','intent':intent,'comparison':result,'story':story,'scheduled':False}

    @app.get('/api/graph-summary')
    def graph_summary(request:Request):
        return {'zones':request.app.state.db.summary(),'source':'Neo4j','aqi_standard':'US'}

    return app

app = create_app()
