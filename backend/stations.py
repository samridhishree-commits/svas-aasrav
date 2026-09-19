"""Current station observations, requested fresh; no feed cache or history archive."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import math
import httpx
from .errors import ServiceError
from .models import Coordinate
from .sampling import distance_m


class StationAirQualityProvider:
    def __init__(self, settings, http):
        self.settings, self.http = settings, http

    def _reading(self, key):
        lat,lng=key
        try:
            response=self.http.get(f'https://api.waqi.info/feed/geo:{lat};{lng}/',
                params={'token':self.settings.waqi_api_token})
            response.raise_for_status()
            payload=response.json()
            if payload.get('status')!='ok':
                raise ServiceError('WAQI rejected the station request. Check WAQI_API_TOKEN and your provider quota.',502,'WAQI_ACCESS')
            data=payload['data']
            raw=data['aqi']
            if isinstance(raw,bool):raise ValueError('Invalid AQI')
            aqi=float(raw)
            if not math.isfinite(aqi) or aqi<0:raise ValueError('Invalid AQI')
            station=Coordinate(lat=data['city']['geo'][0],lng=data['city']['geo'][1]).model_dump()
            distance=distance_m({'lat':lat,'lng':lng},station)/1000
            if distance>self.settings.station_max_distance_km:
                raise ServiceError(f'No station within {self.settings.station_max_distance_km:g} km of one or more route samples. A local AQI comparison is unavailable for this trip.',503,'STATION_COVERAGE')
            observed=datetime.fromisoformat(data['time']['iso'].replace('Z','+00:00'))
            if observed.tzinfo is None or abs(datetime.now(timezone.utc)-observed)>timedelta(hours=6):
                raise ServiceError('A nearby station has no fresh reading within six hours. Please retry later; stale data was not used.',503,'STALE_AQI')
            credits=[{'name':str(a['name']),'url':str(a['url'])} for a in data.get('attributions',[]) if a.get('name') and str(a.get('url','')).startswith(('https://','http://'))]
            return {'aqi':aqi,'standard':'US','source':'WAQI / monitoring stations',
                'data_type':'nearest_station_estimate','observed_at':observed.isoformat(),
                'grid_lat':station['lat'],'grid_lng':station['lng'],'zone_id':f"waqi:{data['idx']}",
                'station_name':data['city']['name'],'station_distance_km':round(distance,2),
                'attributions':credits}
        except ServiceError:raise
        except (httpx.HTTPError,KeyError,ValueError,TypeError,IndexError):
            # Never surface exception URLs: WAQI requires the token in the query string.
            raise ServiceError('Fresh station AQI is unavailable. No regional or invented readings were substituted.',502,'WAQI_UNAVAILABLE') from None

    def readings(self,points):
        keys=[(round(p['lat'],4),round(p['lng'],4)) for p in points]
        unique=list(dict.fromkeys(keys))
        with ThreadPoolExecutor(max_workers=6) as pool:
            resolved=dict(zip(unique,pool.map(self._reading,unique),strict=True))
        return [dict(resolved[key]) for key in keys]
