import math
import threading
import time
from datetime import datetime, timezone, timedelta
import httpx
from .errors import ServiceError
from .models import Coordinate

class AirQualityProvider:
    def __init__(self, settings, http):
        self.settings, self.http = settings, http
        self.cache = {}
        self.lock = threading.Lock()

    def readings(self, points):
        keys = [(round(p['lat'],4), round(p['lng'],4)) for p in points]
        now = time.monotonic()
        with self.lock:
            resolved = {k:self.cache[k][1] for k in set(keys) if k in self.cache and now-self.cache[k][0]<600}
        missing = list(dict.fromkeys(k for k in keys if k not in resolved))
        if missing:
            try:
                response = self.http.get(self.settings.open_meteo_base_url, params={
                    'latitude':','.join(str(k[0]) for k in missing),
                    'longitude':','.join(str(k[1]) for k in missing),
                    'current':'us_aqi,pm2_5,pm10','timezone':'UTC'})
                response.raise_for_status()
                payload = response.json()
                entries = payload if isinstance(payload,list) else [payload]
                if len(entries) != len(missing):
                    raise ValueError('Incomplete coverage')
                updates = {}
                for key, entry in zip(missing, entries):
                    current = entry['current']
                    aqi = current['us_aqi']
                    if isinstance(aqi,bool) or not isinstance(aqi,(int,float)) or not math.isfinite(aqi) or aqi<0:
                        raise ValueError('Missing AQI')
                    timestamp = datetime.fromisoformat(current['time']).replace(tzinfo=timezone.utc)
                    if abs(datetime.now(timezone.utc)-timestamp)>timedelta(hours=6):
                        raise ServiceError('Open-Meteo returned stale air-quality data. Try again later.', 503, 'STALE_AQI')
                    point = Coordinate(lat=entry['latitude'],lng=entry['longitude'])
                    reading = {'aqi':float(aqi),'standard':'US','source':'Open-Meteo / CAMS',
                        'observed_at':timestamp.isoformat(),'grid_lat':point.lat,'grid_lng':point.lng,
                        'pm2_5':current.get('pm2_5'),'pm10':current.get('pm10')}
                    updates[key]=(now,reading)
                    resolved[key]=reading
                with self.lock:
                    if len(self.cache)>2000:
                        self.cache.clear()
                    self.cache.update(updates)
            except ServiceError:
                raise
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                raise ServiceError('Air-quality data is unavailable. No exposure estimate can be calculated.', 502, 'AQI_UNAVAILABLE') from None
        return [dict(resolved[k]) for k in keys]
