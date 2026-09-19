import {useEffect,useRef,useState} from 'react';
import {Sparkles,Send,Users,Clock3,ShieldCheck,CalendarClock} from 'lucide-react';
import {suggestFleet} from './api';
import LiveRouteMap from './LiveRouteMap';
import RoutePollutionProfile from './RoutePollutionProfile';

export default function AdminPlanner(){
  const [prompt,setPrompt]=useState(''),[history,setHistory]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[response,setResponse]=useState(null),[selected,setSelected]=useState('');
  const controller=useRef(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  async function submit(e){
    e.preventDefault();if(loading)return;
    const text=prompt.trim();if(text.length<5)return;
    const previous=history.filter(m=>m.role==='user').slice(-3).map(m=>m.text);
    setHistory(h=>[...h,{role:'user',text}]);setPrompt('');setLoading(true);setError('');setResponse(null);
    const abort=new AbortController();controller.current=abort;
    try{
      const data=await suggestFleet([...previous,text].map((t,i)=>`User message ${i+1}: ${t}`).join('\n').slice(-3000),abort.signal);
      if(data.status!=='ready'){setHistory(h=>[...h,{role:'assistant',text:data.message}]);return}
      setResponse(data);setSelected(data.comparison.recommended_route_id||data.comparison.green_route_id);
      setHistory(h=>[...h,{role:'assistant',text:data.comparison.recommended_route_id?`Compared ${data.comparison.routes.length} routes for your ${data.intent.rider_count} riders. The lowest-exposure qualifying option is highlighted below. Nothing has been scheduled.`:'No available route meets every requirement. Review the reasons below; nothing has been scheduled.'}]);
    }catch(e){if(e.name!=='AbortError')setError(e.message)}finally{setLoading(false)}
  }
  const result=response?.comparison;
  return <>
    <div className="page-heading"><div><div className="eyebrow greeting">LOOKING AFTER YOUR PEOPLE</div><h1>A thoughtful plan for your fleet<span>.</span></h1><p>Describe your team and delivery requirements. Review route suggestions before making a decision.</p></div><span className="connection-badge"><Users size={15}/>Fleet advisor</span></div>
    <div className="scenario-banner live-banner"><span className="scenario-icon"><CalendarClock size={20}/></span><div><strong>Suggestions today. Scheduling comes next.</strong><p>No riders are assigned, notified or dispatched from this dashboard.</p></div><span className="tiny-badge">SCHEDULING COMING SOON</span></div>
    <section className="gemini-planner fleet-conversation"><div className="gemini-heading"><span className="gemini-icon"><Sparkles size={20}/></span><div><span className="eyebrow">YOUR OPERATIONS ASSISTANT</span><h2>What does your team need?</h2></div></div>
      <div className="fleet-messages" aria-live="polite">{history.length?history.map((m,i)=><div key={i} className={`fleet-message ${m.role}`}><small>{m.role==='user'?'YOU':'FLEET ADVISOR'}</small><p>{m.text}</p></div>):<div className="fleet-welcome"><p>Try a request with the number of riders, mask status, pickup, destination and any limits.</p><button className="outline-button" onClick={()=>setPrompt('I have 5 unmasked riders at Saket. Route them to Rohini but absolutely avoid any zones with AQI over 300.')}>5 unmasked riders from Saket to Rohini, avoid AQI over 300</button></div>}</div>
      <form onSubmit={submit} className="gemini-prompt-form"><label className="sr-only" htmlFor="fleet-prompt">Describe your fleet request</label><textarea id="fleet-prompt" value={prompt} onChange={e=>setPrompt(e.target.value)} rows={3} minLength={5} maxLength={1500} required placeholder="I have 5 unmasked riders at Saket. Suggest routes to Rohini, avoiding AQI over 300."/><button className="primary-button" disabled={loading||prompt.trim().length<5}>{loading?<><span className="spinner"/>Finding suggestions...</>:<>Suggest routes<Send size={16}/></>}</button></form>
      <p className="gemini-footnote">Follow up to change a requirement. One shared journey per group. Limits use US AQI. Unmasked riders also exclude sampled AQI above 200.</p>
      {error&&<p className="form-error" role="alert">{error}</p>}
    </section>
    {result&&<>
      <div className="analyst-facts fleet-facts"><div><span>Riders</span><strong><Users size={16}/> {response.intent.rider_count}</strong></div><div><span>Mask status</span><strong>{result.constraints.has_mask?'All masked':'All unmasked'}</strong></div><div><span>Delivery window</span><strong>{result.constraints.delivery_window_minutes} min</strong></div><div><span>Sampled AQI limit</span><strong>{result.constraints.max_aqi?`Below ${result.constraints.max_aqi}`:'No requested limit'}</strong></div></div>
      {response.intent.deadline_assumed&&<p className="constraint-note">No deadline was specified. We used a 90-minute planning window; send a follow-up to change it.</p>}
      <div className="ride-layout live-ride-layout"><section className="planner-panel"><div className="section-heading"><h2>Suggestions to review</h2><span className="tiny-badge">{result.routes.length} OPTIONS</span></div>
        {!result.recommended_route_id&&<div className="deadline-alert" role="alert"><ShieldCheck size={18}/><div><strong>No qualifying route</strong><p>Every available option fails at least one requirement. We have not relaxed your limits.</p></div></div>}
        <div className="route-options">{result.routes.map((r,i)=><button className={`route-card ${r.id===selected?'selected':''}`} key={r.id} onClick={()=>setSelected(r.id)} aria-pressed={r.id===selected}><div className="route-card-top"><strong>Option {i+1}</strong><span className="route-tag">{r.id===result.recommended_route_id?'LOWEST EXPOSURE':r.eligible?'QUALIFIES':'DOES NOT QUALIFY'}</span></div><p className="route-via">{r.description}</p><div className="route-metrics"><Clock3 size={14}/><b>{Math.ceil(r.duration_seconds/60)} min</b><span>{r.average_aqi} avg US AQI</span></div><p className="gemini-footnote">{Math.round(r.exposure_index).toLocaleString()} exposure index per rider</p>{r.constraint_failures.map(reason=><p key={reason} className="route-failure">{reason}</p>)}</button>)}</div>
        <button className="primary-button show-ride" disabled title="Scheduling is not available yet"><CalendarClock size={16}/>Schedule riders — coming soon</button>
      </section><div className="map-column"><LiveRouteMap routes={result.routes} standardRouteId={result.standard_route_id} greenRouteId={result.green_route_id} selectedRouteId={selected} onSelect={setSelected} stationMode={result.aqi_source.startsWith('WAQI')} noRecommendation={!result.recommended_route_id}/></div></div>
      {response.story&&<section className="exposure-analyst"><span className="eyebrow">WHY THIS SUGGESTION</span><h2>{response.story.headline}</h2><p>{response.story.summary}</p><p>{response.story.tradeoff}</p><p className="gemini-footnote">{response.story.caveat}</p></section>}
      <RoutePollutionProfile result={result} selectedRouteId={selected} onSelect={setSelected}/>
      <p className="gemini-footnote">Group suggestions compare the same journey for each rider; rider availability and delivery capacity are not verified. Estimated driving times exclude live traffic.</p>
      <div className="data-note"><p>Air-quality attribution: <a href="https://waqi.info/" target="_blank" rel="noreferrer">World Air Quality Index Project</a>{result.attributions?.filter(a=>!a.name.includes('World Air Quality')).map(a=><span key={a.url}> / <a href={a.url} target="_blank" rel="noreferrer">{a.name}</a></span>)}. Nearby station observations estimate conditions along the road.</p></div>
    </>}
  </>;
}
