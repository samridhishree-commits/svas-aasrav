import { useCallback, useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Layers, MapPin, Wind, Leaf, LocateFixed } from 'lucide-react';
import { usAqiLabel } from './api';

const EMPTY = [];
maplibregl.setWorkerUrl(workerUrl);
const STYLE = import.meta.env.VITE_MAP_STYLE_URL || 'https://tiles.openfreemap.org/styles/positron';
const collection = features => ({type:'FeatureCollection',features});
const line = route => ({type:'Feature',properties:{id:route.id},geometry:{type:'LineString',coordinates:route.coordinates.map(p=>[p.lng,p.lat])}});

export default function LiveRouteMap({routes=EMPTY,standardRouteId,greenRouteId,selectedRouteId,onSelect,noRecommendation=false,stationMode=false}) {
  const container=useRef(null),mapRef=useRef(null),selectRef=useRef(onSelect);
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[attempt,setAttempt]=useState(0),[showAqi,setShowAqi]=useState(true);
  useEffect(()=>{selectRef.current=onSelect},[onSelect]);

  useEffect(()=>{
    let map;
    setReady(false);setError('');
    try {
      map=new maplibregl.Map({container:container.current,style:STYLE,center:[77.209,28.6139],zoom:10.5,
        attributionControl:{compact:true},maxZoom:18});
    } catch {
      setError('Your browser could not start the interactive map. Enable hardware acceleration or try another browser.');
      return;
    }
    mapRef.current=map;
    const timeout=setTimeout(()=>setError('The map is taking too long to load. Check your connection and retry.'),25000);
    map.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
    map.addControl(new maplibregl.FullscreenControl(),'top-right');
    map.on('load',()=>{
      clearTimeout(timeout);
      for(const id of ['standard','green','selection']) map.addSource(id,{type:'geojson',data:collection([])});
      map.addLayer({id:'route-selection',type:'line',source:'selection',layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#fff','line-width':11,'line-opacity':0.95}});
      map.addLayer({id:'route-standard',type:'line',source:'standard',layout:{'line-join':'round'},paint:{'line-color':'#717e8e','line-width':5,'line-dasharray':[2,1.5]}});
      map.addLayer({id:'route-green',type:'line',source:'green',layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#267b58','line-width':6}});
      for(const id of ['route-standard','route-green']) {
        map.on('click',id,event=>{const routeId=event.features?.[0]?.properties?.id;if(routeId)selectRef.current?.(routeId)});
        map.on('mouseenter',id,()=>{map.getCanvas().style.cursor='pointer'});
        map.on('mouseleave',id,()=>{map.getCanvas().style.cursor=''});
      }
      setReady(true);setError('');
    });
    map.on('error',()=>setError('Some map data could not load. Check your connection or retry the map; route results remain available.'));
    const observer=new ResizeObserver(()=>map.resize());observer.observe(container.current);
    return()=>{clearTimeout(timeout);observer.disconnect();mapRef.current=null;map.remove()};
  },[attempt]);

  const fit=useCallback(()=>{
    const map=mapRef.current;
    if(!map||!ready||!routes.length)return;
    const bounds=new maplibregl.LngLatBounds();
    routes.forEach(route=>route.coordinates.forEach(p=>bounds.extend([p.lng,p.lat])));
    if(!bounds.isEmpty())map.fitBounds(bounds,{padding:{top:85,bottom:115,left:45,right:45},maxZoom:14,duration:500});
  },[routes,ready]);
  useEffect(()=>{fit()},[fit]);
  useEffect(()=>{
    const map=mapRef.current;if(!map||!ready)return;
    map.getSource('standard').setData(collection(routes.filter(r=>r.id!==greenRouteId).map(line)));
    map.getSource('green').setData(collection(routes.filter(r=>r.id===greenRouteId).map(line)));
    map.setPaintProperty('route-green','line-color',noRecommendation?'#b18345':'#267b58');
    map.getSource('selection').setData(collection(routes.filter(r=>r.id===selectedRouteId).map(line)));
  },[routes,greenRouteId,selectedRouteId,ready,noRecommendation]);

  useEffect(()=>{
    const map=mapRef.current;if(!map||!ready)return;
    const current=routes.find(r=>r.id===selectedRouteId)||routes.find(r=>r.id===greenRouteId)||routes[0];
    if(!current)return;
    const markers=[],popups=[];
    [current.coordinates[0],current.coordinates.at(-1)].forEach((point,index)=>{
      const element=document.createElement('div');element.className='live-endpoint';element.textContent=index?'B':'A';
      element.setAttribute('aria-label',index?'Drop road access':'Pickup road access');
      markers.push(new maplibregl.Marker({element}).setLngLat([point.lng,point.lat]).addTo(map));
    });
    if(showAqi)current.samples?.forEach(point=>{
      const element=document.createElement('button');element.type='button';element.className=`live-aqi-marker ${point.aqi>200?'high':''}`;
      element.setAttribute('aria-label',`Estimated US AQI ${Math.round(point.aqi)}`);
      const content=document.createElement('div');content.className='live-info-window';
      const provenance=point.station_name?`${point.station_name} (${point.station_distance_km} km from sample). Nearby station proxy.`:'Regional model estimate, not a street sensor.';
      for(const [tag,text] of [['strong',`${Math.round(point.aqi)} US AQI`],['p',usAqiLabel(point.aqi)],['small',`${point.source||'Regional estimate'} | ${new Date(point.observed_at).toLocaleString()}. ${provenance}`]]) {
        const child=document.createElement(tag);child.textContent=text;content.append(child);
      }
      const popup=new maplibregl.Popup({offset:14,maxWidth:'260px'}).setDOMContent(content);popups.push(popup);
      const marker=new maplibregl.Marker({element}).setLngLat([point.lng,point.lat]).setPopup(popup).addTo(map);
      element.addEventListener('click',()=>{popups.forEach(p=>{if(p!==popup)p.remove()})});markers.push(marker);
    });
    return()=>{popups.forEach(p=>p.remove());markers.forEach(m=>m.remove())};
  },[routes,greenRouteId,selectedRouteId,ready,showAqi]);

  return <div className="map-panel live-map-panel">
    <div ref={container} className="live-map-canvas" aria-label="Interactive Delhi NCR map"/>
    {!ready&&!error&&<div className="map-unavailable" role="status"><span className="spinner green-spinner"/><p>Loading your open-source map…</p></div>}
    {error&&<div className={ready?'map-service-error':'map-unavailable map-error'} role="status"><MapPin size={22}/><p>{error}</p><button className="outline-button" onClick={()=>setAttempt(n=>n+1)}>Retry map</button></div>}
    <div className="map-top"><div className="map-location"><span className="green-dot"/>Delhi NCR<span className="map-divider">/</span><span>Road map</span></div><button className={`map-layer ${showAqi?'enabled':''}`} aria-pressed={showAqi} onClick={()=>setShowAqi(!showAqi)}><Layers size={15}/>AQI samples<span className="mini-toggle"/></button></div>
    {routes.length>0&&ready&&<button className="live-recenter" aria-label="Fit routes on map" onClick={fit}><LocateFixed size={19}/></button>}
    <div className="map-insight live-map-insight"><div className="insight-icon"><Leaf size={19}/></div><div><strong>{routes.length?(stationMode?'Real roads. Nearby monitoring stations.':'Real roads. Regional air-quality estimates.'):'Your next journey starts here.'}</strong><p>{routes.length?(noRecommendation?'No qualifying route. Amber and grey paths are comparison options only.':standardRouteId===greenRouteId?'Fastest and lowest-exposure routes coincide.':'Solid green: lowest-exposure · dashed grey: alternatives'):'Enter your pickup and drop location to compare routes.'}</p></div><Wind className="insight-wind" size={23}/></div>
  </div>;
}
