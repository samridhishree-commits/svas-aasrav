"""Live integration check: Photon geocoding, OSRM, Open-Meteo and Neo4j."""
import json
import httpx
from .config import Settings
from .database import Database
from .providers import AirQualityProvider
from .openstreetmap import OpenStreetMapProvider
from .service import RoutingService
from .models import RouteRequest
from .errors import ServiceError

if __name__=='__main__':
    settings=Settings()
    db=Database(settings)
    try:
        with httpx.Client(timeout=30) as http:
            service=RoutingService(settings,OpenStreetMapProvider(settings,http),AirQualityProvider(settings,http),db)
            result=service.calculate(RouteRequest(pickup='Saket',drop='Rohini',delivery_window_minutes=120))
            assert result['routes'] and all(len(r['coordinates'])>2 for r in result['routes'])
            assert result['ranking_engine']=='Neo4j Cypher'
            print(json.dumps({'status':'ok','test':'actual Photon geocoding + OSRM + Open-Meteo + Neo4j',
                'routes':len(result['routes']),'graph':result['graph'],'lower_aqi_percent':result['lower_aqi_percent'],
                'exposure_reduction_percent':result['exposure_reduction_percent'],
                'durations_minutes':[round(r['duration_seconds']/60,1) for r in result['routes']],
                'aqi':[r['average_aqi'] for r in result['routes']]}))
    except ServiceError as error:
        print(json.dumps({'status':'error','code':error.code,'message':error.message}))
        raise SystemExit(1)
    finally:
        db.close()
