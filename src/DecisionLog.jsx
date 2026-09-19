import {ClipboardList,CheckCircle2,AlertCircle,Clock3} from 'lucide-react';

export default function DecisionLog({result,loading=false,selectedRouteId}){
  if(!result&&!loading)return null;
  const saved=result?.activity_log_status==='saved';
  return <section className="decision-log" aria-label="Decision log">
    <div className="section-heading"><h2><ClipboardList size={17}/>Decision log</h2><span className="tiny-badge">{loading?'PROCESSING':saved?'SAVED RECORD':'UNAVAILABLE'}</span></div>
    {loading?<p className="log-pending"><span className="spinner green-spinner"/>Comparing your options. Verified activity will appear when the comparison completes.</p>:!saved?<p className="constraint-note">The saved log is unavailable for this comparison. Your route results are still usable.</p>:<>
      <p className="log-caption">Recorded during this comparison. Highlighted entries match your selected route.</p>
      <ol>{result.activity_log.map(event=><li key={event.id} className={`${event.level} ${event.route_id===selectedRouteId?'log-selected':''}`}>
        {event.level==='warning'?<AlertCircle size={15}/>:event.level==='success'?<CheckCircle2 size={15}/>:<Clock3 size={15}/>}
        <div><span className="log-stage">{event.stage.replaceAll('_',' ')}<time dateTime={event.recorded_at}>{new Date(event.recorded_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time></span><p>{event.message}</p></div>
      </li>)}</ol>
      <details className="log-reference"><summary>Comparison reference</summary><code>{result.trip_id}</code><p>Use this reference to find the same record in your database console.</p></details>
    </>}
  </section>;
}
