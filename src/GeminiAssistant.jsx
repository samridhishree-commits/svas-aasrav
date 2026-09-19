import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowRight, CircleHelp, Sparkles } from 'lucide-react';
import { parseTrip, analyzeExposure } from './api';

export function NaturalLanguagePlanner({defaults,onApply,formVersion}) {
  const [prompt,setPrompt]=useState(''),[loading,setLoading]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const requestRef=useRef(null);
  useEffect(()=>()=>requestRef.current?.abort(),[]);
  useEffect(()=>{requestRef.current?.abort();setLoading(false)},[formVersion]);
  async function submit(event) {
    event.preventDefault();requestRef.current?.abort();setError('');setMessage('');
    const controller=new AbortController();requestRef.current=controller;setLoading(true);
    try {
      const data=await parseTrip({prompt:prompt.trim(),...defaults},controller.signal);
      if(controller.signal.aborted)return;
      if(data.status==='ready'){setMessage('Trip details filled. Finding your routes...');await onApply(data.payload)}
      else setMessage(data.message);
    } catch(e){if(e.name!=='AbortError')setError(e.message)}
    finally{if(requestRef.current===controller)setLoading(false)}
  }
  return <section className="gemini-planner" aria-labelledby="gemini-plan-title">
    <div className="gemini-heading"><span className="gemini-icon"><Sparkles size={20}/></span><div><span className="eyebrow">YOUR PERSONAL ROUTE ASSISTANT</span><h2 id="gemini-plan-title">Tell us about your journey.</h2></div><span className="tiny-badge">AI TRIP PLANNER</span></div>
    <form onSubmit={submit} className="gemini-prompt-form"><label className="sr-only" htmlFor="trip-prompt">Describe your trip</label><textarea id="trip-prompt" value={prompt} minLength={5} maxLength={1500} required rows={2} placeholder="Take me from Saket to Rohini within an hour, with AQI below 300. I have a mask." onChange={e=>{requestRef.current?.abort();setLoading(false);setMessage('');setError('');setPrompt(e.target.value)}}/><button className="primary-button" disabled={loading||prompt.trim().length<5}>{loading?<><span className="spinner"/>Understanding…</>:<>Find my routes<ArrowDown size={16}/></>}</button></form>
    <p className="gemini-footnote">Describe your journey in English or Hinglish. We fill the details and find routes automatically. Limits use US AQI.</p>
    {message&&<p className="gemini-message" role="status"><CircleHelp size={16}/>{message}</p>}
    {error&&<p className="form-error" role="alert">{error}</p>}
  </section>;
}

export function ExposureAnalyst({result,selectedRouteId,dirty}) {
  const [analysis,setAnalysis]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
  const requestRef=useRef(null);
  useEffect(()=>()=>requestRef.current?.abort(),[]);
  useEffect(()=>{if(dirty){requestRef.current?.abort();setLoading(false)}},[dirty]);
  async function explain() {
    requestRef.current?.abort();const controller=new AbortController();requestRef.current=controller;
    setLoading(true);setError('');setAnalysis(null);
    try {
      const next=await analyzeExposure(result.trip_id,selectedRouteId,controller.signal);
      if(!controller.signal.aborted)setAnalysis(next);
    }catch(e){if(e.name!=='AbortError')setError(e.message)}
    finally{if(requestRef.current===controller)setLoading(false)}
  }
  const route=result.routes.find(r=>r.id===selectedRouteId),fastest=result.routes.find(r=>r.id===result.standard_route_id);
  const extra=route&&fastest?Math.round((route.duration_seconds-fastest.duration_seconds)/60):0;
  return <section className="exposure-analyst" aria-labelledby="analyst-title">
    <div className="gemini-heading"><span className="gemini-icon"><Sparkles size={20}/></span><div><span className="eyebrow">YOUR ROUTE, EXPLAINED</span><h2 id="analyst-title">Exposure analyst</h2></div><span className="tiny-badge">ROUTE INSIGHTS</span></div>
    <p className="analyst-intro">Understand the selected route’s time and pollution tradeoff, using your current route comparison.</p>
    <div className="analyst-facts"><div><span>Selected route</span><strong>{route?Math.ceil(route.duration_seconds/60):'—'} <small>min</small></strong></div><div><span>Compared with fastest</span><strong>{extra>0?'+':''}{extra} <small>min</small></strong></div><div><span>Average US AQI</span><strong>{route?Math.round(route.average_aqi):'—'}</strong></div><div><span>Your preferences</span><strong className="analyst-eligibility">{route?.eligible?'Met by samples':'Not met'}</strong></div></div>
    {dirty?<p className="gemini-message">Your preferences changed. Show your ride again before requesting an explanation.</p>:<>
      {analysis&&<div className="analyst-story" aria-live="polite"><h3>{analysis.story.headline}</h3><p>{analysis.story.summary}</p><div className="analyst-story-grid"><div><span>THE TRADEOFF</span><p>{analysis.story.tradeoff}</p></div><div><span>KEEP IN MIND</span><p>{analysis.story.caveat}</p></div></div></div>}
      {error&&<p className="form-error" role="alert">{error}</p>}
      <button className="outline-button analyst-button" onClick={explain} disabled={loading}>{loading?<><span className="spinner green-spinner"/>Explaining your comparison…</>:<><Sparkles size={15}/>{analysis?'Explain again':'Explain this route'}<ArrowRight size={15}/></>}</button>
    </>}
    <p className="gemini-footnote">AI-written explanation of this comparison. Routes are ranked by exposure within your requirements. Air-quality estimates are not personal exposure measurements.</p>
  </section>;
}
