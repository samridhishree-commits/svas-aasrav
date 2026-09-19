from uuid import uuid4
from math import ceil
from datetime import datetime, timezone
from .errors import ServiceError
from .sampling import distance_m, sample_route, reduction_percent

class RoutingService:
    def __init__(self, settings, maps, air, database):
        self.settings, self.maps, self.air, self.database = settings, maps, air, database

    def calculate(self, request, *, rider_count=None):
        events=[]
        def record(stage,message,level='info',route_id=None):
            events.append({'sequence':len(events)+1,'stage':stage,'message':message,'level':level,
                'route_id':route_id,'recorded_at':datetime.now(timezone.utc).isoformat()})
        record('request',f"{'Fleet suggestion for '+str(rider_count)+' riders' if rider_count else 'Rider comparison'} requested. Window: {request.delivery_window_minutes} min; {'masked' if request.has_mask else 'unmasked'}; sampled US AQI {'below '+str(request.max_aqi) if request.max_aqi is not None else 'without a requested ceiling'}.")
        if request.pickup.casefold() == request.drop.casefold():
            raise ServiceError('Choose different pickup and drop locations.', 422, 'SAME_LOCATION')
        # Verify the required database before contacting public map services.
        self.database.ensure_available()
        origin, destination = self.maps.geocode(request.pickup), self.maps.geocode(request.drop)
        if distance_m(origin,destination) < 50:
            raise ServiceError('Pickup and drop are too close to compare routes.', 422, 'SAME_LOCATION')
        record('locations','Pickup and destination matched within the service area.')
        candidates = self.maps.routes(origin,destination,request.travel_mode)
        record('routes',f'{len(candidates)} distinct driving options found, including labelled detours where available.')
        all_samples=[]
        for route in candidates:
            route['samples'] = sample_route(route['path'],route['duration_seconds'],self.settings.route_sample_count)
            all_samples.extend(route['samples'])
        readings = self.air.readings(all_samples)
        for sample,reading in zip(all_samples,readings,strict=True):
            sample.update(reading)
            sample['zone_id'] = reading.get('zone_id') or f"cams:{reading['grid_lat']:.4f}:{reading['grid_lng']:.4f}"
            sample['reading_id'] = f"{sample['zone_id']}:{reading['observed_at']}:{reading['aqi']}"
        station_data=bool(readings[0].get('station_name'))
        source=readings[0]['source']
        credits=list({a['url']:a for r in readings for a in r.get('attributions',[])}.values())
        record('air_quality',f"{len(all_samples)} route samples checked across {len({s['zone_id'] for s in all_samples})} {'monitoring stations' if station_data else 'regional model cells'}. Freshness and coverage checks passed.")
        trip_id = str(uuid4())
        # Neo4j receives the scoring graph; addresses and geometry stay in the response.
        graph_routes=[{'id':r['id'],'duration_seconds':r['duration_seconds'],'samples':r['samples']} for r in candidates]
        ranked = self.database.rank_routes(trip_id,graph_routes,request)
        record('ranking','Route graph evaluated: qualifying options ordered by lowest exposure, then shortest journey time.')
        metrics = {r['id']:r for r in ranked}
        standard = min(candidates,key=lambda r:r['duration_seconds'])
        # If no route fits, expose that explicitly; never imply a constraint was met.
        green_id = ranked[0]['id']
        recommended_id = green_id if ranked[0]['eligible'] else None
        green = next(r for r in candidates if r['id']==green_id)
        normalized=[]
        for route in candidates:
            score = metrics[route['id']]
            late_by = ceil(max(0, route['duration_seconds']/60-request.delivery_window_minutes))
            failures = []
            if late_by:
                failures.append(f'{late_by} min late for your {request.delivery_window_minutes}-minute deadline')
            if request.max_aqi is not None and score['max_sampled_aqi'] >= request.max_aqi:
                failures.append(f"Peak sampled US AQI {score['max_sampled_aqi']:g} does not meet your below-{request.max_aqi} limit")
            if not request.has_mask and score['high_aqi_seconds'] > 0:
                failures.append(f'Unmasked rider: sampled US AQI exceeds {self.settings.high_aqi_threshold:g}')
            option=candidates.index(route)+1
            record('route_check',f"Option {option}: {ceil(route['duration_seconds']/60)} min; exposure index {score['exposure_index']:.1f}. "+('Qualifies.' if score['eligible'] else 'Does not qualify: '+'; '.join(failures)+'.'),
                'success' if score['eligible'] else 'warning',route['id'])
            normalized.append({
                'id':route['id'], 'name':'Lowest-exposure route' if route['id']==recommended_id else 'Standard route' if route['id']==standard['id'] else 'Alternative route',
                'deadline_met':late_by==0,'late_by_minutes':late_by,'constraint_failures':failures,
                'min_sampled_aqi':min(s['aqi'] for s in route['samples']),
                'is_detour':route.get('is_detour',False),
                'description':route['description'].replace('OSRM driving option','Driving option'),'coordinates':route['path'],
                'duration_seconds':route['duration_seconds'],'distance_meters':route['distance_meters'],
                'average_aqi':round(score['average_aqi'],1),'aqi_standard':'US',
                'exposure_index':round(score['exposure_index'],1),'high_aqi_minutes':round(score['high_aqi_seconds']/60,1),
                'routing_cost':round(score['routing_cost'],2),'eligible':score['eligible'],
                'max_sampled_aqi':score['max_sampled_aqi'],
                'observed_at':score['observed_at'],'sample_count':score['sample_count'],
                'samples':[{'lat':s['lat'],'lng':s['lng'],'aqi':s['aqi'],'observed_at':s['observed_at'],'grid_lat':s['grid_lat'],'grid_lng':s['grid_lng'],'source':s['source'],'station_name':s.get('station_name'),'station_distance_km':s.get('station_distance_km')} for s in route['samples']],
            })
        standard_score, green_score = metrics[standard['id']],metrics[green_id]
        warnings = [('AQI uses nearby monitoring stations via WAQI. Station readings are proxies for route samples, not measurements on every street.' if station_data else 'AQI is a current CAMS model estimate at roughly 45 km resolution in Delhi; nearby routes may share identical readings.'),
                    'Exposure index is AQI × estimated minutes, not inhaled dose. Sample time is allocated proportionally to route distance.']
        warnings.append('Driving estimates are provided without live traffic or motorcycle-specific restrictions. Confirm the matched locations and follow road signs.')
        if len(candidates)==1:
            warnings.append('Only one driving route was found; the standard and lowest-exposure routes are identical.')
        elif standard['id']==green_id and recommended_id:
            warnings.append('The fastest route also has the lowest exposure among qualifying options; no different green route is implied.')
        if recommended_id is None:
            warnings.append('No route meets all your delivery, mask and AQI preferences. Review the constraints before travelling.')
        if request.max_aqi is not None:
            warnings.append(f'Your limit requires every sampled US AQI to be below {request.max_aqi}. Samples cannot guarantee conditions along every street.')
        for route in candidates:
            warnings.extend(route['warnings'])
        deadline={'requested_minutes':request.delivery_window_minutes,
            'fastest_minutes':ceil(standard['duration_seconds']/60),
            'minimum_extra_minutes':ceil(max(0,standard['duration_seconds']/60-request.delivery_window_minutes)),
            'any_route_on_time':standard['duration_seconds']<=request.delivery_window_minutes*60}
        if not deadline['any_route_on_time']:
            warnings.insert(0,f"Your {deadline['requested_minutes']}-minute deadline cannot be met: the fastest available route takes {deadline['fastest_minutes']} minutes ({deadline['minimum_extra_minutes']} minutes late), without live traffic.")
        averages=[r['average_aqi'] for r in normalized]
        indistinguishable=max(averages)-min(averages)<0.1
        quality={'data_type':'nearest_station_estimate' if station_data else 'regional_model','model_resolution_km':None if station_data else 45,
            'max_station_distance_km':max((s.get('station_distance_km',0) for s in all_samples),default=0),
            'similar_route_averages':indistinguishable,
            'min_sampled_aqi':min(s['aqi'] for s in all_samples),
            'max_sampled_aqi':max(s['aqi'] for s in all_samples),
            'message':('Available AQI data cannot distinguish pollution between these routes. With matching AQI, a shorter trip reduces the time-based exposure index; it does not have cleaner air.' if indistinguishable else 'Route averages differ based on nearby monitoring stations. Readings are estimates of conditions along each route.' if station_data else 'Route averages differ in the regional model. These are estimates, not street-level pollution measurements.')}
        record('decision',f"Option {next(i+1 for i,r in enumerate(candidates) if r['id']==recommended_id)} suggested: lowest exposure among qualifying routes." if recommended_id else 'No qualifying route. Requirements were not relaxed.',
            'success' if recommended_id else 'warning',recommended_id)
        if rider_count:record('scheduling','Suggestions only. No riders assigned, notified or scheduled.')
        try:
            activity=self.database.save_activity(trip_id,events)
            activity_status='saved'
        except ServiceError:
            activity=[]
            activity_status='unavailable'
            warnings.append('Routes were calculated, but the decision log could not be saved.')
        return {'trip_id':trip_id,'origin':origin,'destination':destination,'routes':normalized,
            'activity_log':activity,'activity_log_status':activity_status,
            'deadline_summary':deadline,'data_quality':quality,
            'standard_route':standard['path'],'green_route':green['path'],
            'standard_route_id':standard['id'],'green_route_id':green_id,'recommended_route_id':recommended_id,
            'lower_aqi_percent':reduction_percent(standard_score['average_aqi'],green_score['average_aqi']),
            'exposure_reduction_percent':reduction_percent(standard_score['exposure_index'],green_score['exposure_index']),
            'aqi_standard':'US','aqi_source':source,'attributions':credits,'ranking_engine':'Neo4j Cypher',
            'routing_source':'OSRM / OpenStreetMap','geocoding_source':'Photon / OpenStreetMap',
            'high_aqi_threshold':self.settings.high_aqi_threshold,'travel_mode':request.travel_mode,
            'constraints':{'delivery_window_minutes':request.delivery_window_minutes,'has_mask':request.has_mask,'max_aqi':request.max_aqi,'aqi_standard':'US'},
            'graph':{'candidate_routes':len(candidates),'samples':len(all_samples),'air_zones':len({s['zone_id'] for s in all_samples})},
            'warnings':list(dict.fromkeys(warnings))}
