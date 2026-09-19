import { Wind } from 'lucide-react';

export default function RoutePollutionProfile({result,selectedRouteId,onSelect}) {
  const maximum=Math.max(200,...result.routes.flatMap(r=>(r.samples||[]).map(s=>s.aqi)));
  return <section className="pollution-profile">
    <div className="section-heading"><div><h2><Wind size={18}/>Air quality along each route</h2><p>Pickup → drop · US AQI at evenly spaced route samples</p></div><span className="tiny-badge">{result.data_quality?.data_type==='nearest_station_estimate'?'NEARBY STATIONS':'REGIONAL ESTIMATES'}</span></div>
    {result.data_quality&&<p className={`pollution-coverage ${result.data_quality.similar_route_averages?'limited':''}`}>{result.data_quality.message}</p>}
    <div className="pollution-comparisons">{result.routes.map((route,index)=>{
      const values=(route.samples||[]).map(s=>s.aqi);
      return <button key={route.id} onClick={()=>onSelect(route.id)} aria-pressed={route.id===selectedRouteId} className={`pollution-row ${route.id===selectedRouteId?'active':''}`}>
        <div className="pollution-route-title"><strong>Route {index+1}</strong><small>{route.description}</small></div>
        <div className="aqi-sparkline" role="img" aria-label={`Route ${index+1} sampled US AQI: ${values.join(', ')}`}>
          {values.map((aqi,i)=><span key={i} title={`Sample ${i+1}: ${aqi} US AQI`} style={{height:`${Math.max(2,aqi/maximum*100)}%`,background:aqi>200?'#895496':aqi>150?'#c56552':aqi>100?'#bd913e':aqi>50?'#b7b65f':'#6d9463'}}/>)}
        </div>
        <div className="pollution-figures"><strong>{Number(route.average_aqi).toFixed(1)} <small>avg US AQI</small></strong><small>{values.length?`${Math.min(...values).toFixed(1)}–${Math.max(...values).toFixed(1)} sampled range`:'Samples unavailable'}</small><small>{Math.round(route.exposure_index||0).toLocaleString()} AQI·min exposure index</small></div>
      </button>;
    })}</div>
    <p className="pollution-profile-note">{result.data_quality?.data_type==='nearest_station_estimate'?`All charts share the same scale. Each sample uses a nearby station, up to ${result.data_quality.max_station_distance_km} km away in this comparison. These are not measurements at every road point.`:'All charts share the same scale. Repeated samples may come from the same ~45 km regional model cell. More samples do not create finer measurements.'}</p>
  </section>;
}
