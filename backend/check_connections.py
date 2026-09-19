"""Check integrations without printing keys, credentials or provider payloads."""
import json
import httpx
from .config import Settings
from .database import Database
from .providers import AirQualityProvider
from .openstreetmap import OpenStreetMapProvider
from .errors import ServiceError

if __name__ == '__main__':
    settings=Settings()
    database=Database(settings)
    with httpx.Client(timeout=25) as client:
        checks=[('neo4j',database.initialize),
                ('photon_geocoding',lambda:OpenStreetMapProvider(settings,client).geocode('Saket, New Delhi')),
                ('open_meteo',lambda:AirQualityProvider(settings,client).readings([{'lat':28.6139,'lng':77.209}]))]
        for name,check in checks:
            try:
                check()
                print(json.dumps({'service':name,'status':'ok'}),flush=True)
            except ServiceError as error:
                print(json.dumps({'service':name,'status':'error','code':error.code,'message':error.message}),flush=True)
            except Exception as error:
                print(json.dumps({'service':name,'status':'error','type':type(error).__name__}),flush=True)
    database.close()
