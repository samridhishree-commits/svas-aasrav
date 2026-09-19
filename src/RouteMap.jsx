import { useState } from 'react';
import { Layers, Plus, Minus, LocateFixed, Wind, ArrowUpRight, X, Leaf } from 'lucide-react';
import { locations, zones, routePoints, aqiLabel } from './data';

const roads = [
  'M-20 110 220 130 420 94 680 114 980 55','M-20 220 170 198 320 230 560 195 920 242','M-20 350 170 308 345 338 595 302 930 346','M-20 452 220 432 400 462 620 416 940 442','M-20 555 190 535 410 577 680 541 930 573',
  'M90 -20 160 130 120 260 190 400 125 660','M290 -20 260 138 306 302 260 470 320 660','M440 -20 420 150 466 260 430 415 485 660','M625 -20 585 160 632 290 590 470 650 660','M780 -20 740 145 780 308 745 480 800 660',
  'M-20 40 210 220 350 230 500 400 715 500 950 600','M30 650 230 450 345 360 540 250 690 180 980 150','M-20 310 170 385 330 385 410 350 520 345 670 390 940 360',
];
export default function RouteMap({ origin, destination, routes, selected, onSelect, winter, activeRide=false, admin=false }) {
  const [showAqi,setShowAqi] = useState(true), [zoom,setZoom] = useState(1), [zone,setZone] = useState(null);
  const selectedRoute = routes.find(r=>r.id===selected) || routes[0];
  return <div className="map-panel">
    <div className="map-top"><div className="map-location"><span className="green-dot" /> Delhi NCR <span className="map-divider">/</span><span>Route overview</span></div><button className={`map-layer ${showAqi?'enabled':''}`} onClick={()=>setShowAqi(!showAqi)} aria-pressed={showAqi}><Layers size={15}/> AQI layer <span className="mini-toggle"/></button></div>
    <svg className="delhi-map" viewBox="0 0 940 640" role="img" aria-label="Illustrative map of Delhi with simulated air quality and selectable routes">
      <defs>
        <pattern id="blocks" width="68" height="58" patternUnits="userSpaceOnUse" patternTransform="rotate(-12)"><rect width="68" height="58" fill="#edeee7"/><rect x="5" y="5" width="24" height="20" rx="3" fill="#e3e5dd"/><rect x="35" y="5" width="28" height="20" rx="3" fill="#e6e7df"/><rect x="5" y="32" width="39" height="20" rx="3" fill="#e5e7de"/><rect x="49" y="32" width="14" height="20" rx="2" fill="#e1e5dc"/><path d="M0 28H68M32 0V28M46 28V58" stroke="#fafaf5" strokeWidth="4"/></pattern>
        <radialGradient id="severe"><stop stopColor="#e69d85" stopOpacity=".53"/><stop offset="1" stopColor="#e69d85" stopOpacity=".06"/></radialGradient>
        <radialGradient id="poor"><stop stopColor="#e7bb79" stopOpacity=".48"/><stop offset="1" stopColor="#e7bb79" stopOpacity=".07"/></radialGradient>
        <radialGradient id="moderate"><stop stopColor="#bfd495" stopOpacity=".5"/><stop offset="1" stopColor="#bfd495" stopOpacity=".05"/></radialGradient>
        <filter id="labelShadow"><feDropShadow dx="0" dy="2" stdDeviation="4" floodOpacity=".10"/></filter>
      </defs>
      <rect width="940" height="640" fill="url(#blocks)"/>
      <g transform={`translate(${470*(1-zoom)} ${320*(1-zoom)}) scale(${zoom})`}>
        <path d="M810-30C720 60 803 151 757 244S816 357 783 438 837 565 810 670" fill="none" stroke="#b8d5d7" strokeWidth="29"/>
        <path d="M809-30C720 60 803 151 757 244S816 357 783 438 837 565 810 670" fill="none" stroke="#cce4e5" strokeWidth="15"/>
        <g fill="#d7e0c6" stroke="#cdd8bd"><path d="m350 398 68-13 35 42-28 95-55-12-25-70Z"/><path d="m525 433 56 5 17 42-33 32-47-18Z"/><path d="m146 46 43-4 28 32-10 42-45-14Z"/><path d="m670 85 44 11 12 51-32 17-35-38Z"/><path d="m90 480 51 8 21 39-25 32-59-21Z"/><path d="m810 302 45-14 46 39-17 46-58-17Z"/><path d="m480 48 54-2 10 46-31 17-43-18Z"/></g>
        {roads.map((d,i)=><path key={`edge${i}`} d={d} fill="none" stroke="#d3d5cd" strokeWidth="11" strokeLinejoin="round"/>)}
        {roads.map((d,i)=><path key={i} d={d} fill="none" stroke="#fcfcf8" strokeWidth="8" strokeLinejoin="round"/>)}
        <path d="M190 140 330 165 490 220 667 306 672 465 480 515 322 462 185 315Z" fill="none" stroke="#e6d8b6" strokeWidth="13" strokeLinejoin="round"/>
        <path d="M190 140 330 165 490 220 667 306 672 465 480 515 322 462 185 315Z" fill="none" stroke="#fff6dd" strokeWidth="9" strokeLinejoin="round"/>
        <g className="map-street-text"><text x="381" y="447" transform="rotate(-75 381 447)">DELHI RIDGE</text><text x="813" y="390" transform="rotate(82 813 390)">YAMUNA RIVER</text><text x="498" y="505" transform="rotate(-14 498 505)">OUTER RING ROAD</text><text x="322" y="183" transform="rotate(20 322 183)">RING ROAD</text></g>
        <g className="map-city-label"><text x="92" y="225">PASCHIM VIHAR</text><text x="312" y="78">PITAMPURA</text><text x="542" y="149">MODEL TOWN</text><text x="675" y="270">OLD DELHI</text><text x="385" y="368" className="main-city">NEW DELHI</text><text x="180" y="401">DELHI CANTONMENT</text><text x="602" y="587">SOUTH DELHI</text><text x="826" y="423">EAST DELHI</text></g>
        {showAqi && zones.map(z=><g key={z.id} className="zone-hit" onClick={()=>setZone(z)} role="button" tabIndex="0" aria-label={`${z.name} simulated AQI ${winter?z.value:Math.round(z.value*.5)}`} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setZone(z)}}}>
          <circle cx={z.x} cy={z.y} r={z.radius} fill={`url(#${winter?z.kind:'moderate'})`} stroke={winter&&z.value>400?'#dcad99':'#d1ba95'} strokeOpacity=".5" strokeDasharray="4 5"/>
          <rect x={z.x-32} y={z.y-12} width="64" height="28" rx="14" fill="#fffdf8" filter="url(#labelShadow)"/><circle cx={z.x-18} cy={z.y+2} r="3.5" fill={winter&&z.value>300?'#da8868':'#99a858'}/><text x={z.x+6} y={z.y+7} className="aqi-map-value">{winter?z.value:Math.round(z.value*.5)}</text>
          <text x={z.x} y={z.y+33} className="station-name">{z.name}</text>
        </g>)}
        {[...routes].sort((a,b)=>(a.id===selected?1:0)-(b.id===selected?1:0)).map(r=><g key={r.id} className="route-path" onClick={()=>onSelect(r.id)}>
          <polyline points={routePoints(origin,destination,r.id).map(p=>p.join(',')).join(' ')} fill="none" stroke="white" strokeWidth={r.id===selected?11:8} strokeLinejoin="round" strokeLinecap="round"/>
          <polyline points={routePoints(origin,destination,r.id).map(p=>p.join(',')).join(' ')} fill="none" stroke={r.color} strokeWidth={r.id===selected?6:4} strokeLinejoin="round" strokeLinecap="round" opacity={r.id===selected?1:.65}/>
        </g>)}
        {locations.filter(l=>![origin.id,destination.id].includes(l.id)).map(l=><text key={l.id} x={l.x} y={l.y} className="locality-label">{l.name.toUpperCase()}</text>)}
        {[origin,destination].map((p,i)=><g key={i}><circle cx={p.x} cy={p.y} r="15" fill="white" opacity=".5"/><circle cx={p.x} cy={p.y} r="10" fill={i?'#244f3b':'white'} stroke="#277b58" strokeWidth="4"/>{i&&<path d={`m${p.x-3} ${p.y} 2 2 4-5`} stroke="white" strokeWidth="1.5" fill="none"/>}<rect x={p.x+20} y={p.y-17} width={p.name.length*7.2+22} height="32" rx="7" fill="white" filter="url(#labelShadow)"/><text x={p.x+31} y={p.y+4} className="endpoint-label">{p.name}</text></g>)}
        {selectedRoute&&<g transform={`translate(${(origin.x+destination.x)/2-95} ${(origin.y+destination.y)/2+45})`} filter="url(#labelShadow)"><rect width="105" height="42" rx="10" fill="#277b58"/><text x="52" y="26" fill="white" textAnchor="middle" fontSize="15" fontWeight="700">{selectedRoute.minutes} min</text></g>}
        {admin&&<g fill="#176348" stroke="white" strokeWidth="3"><circle cx="270" cy="210" r="8"/><circle cx="485" cy="400" r="8"/><circle cx="580" cy="270" r="8"/><circle cx="330" cy="440" r="8"/></g>}
      </g>
    </svg>
    <div className="map-caption">Illustrative Delhi map <span>•</span> Simulated AQI (IN)</div>
    <div className="map-controls"><button title="Zoom in" aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(1.8,z+.2))}><Plus size={19}/></button><button title="Zoom out" aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(.8,z-.2))}><Minus size={19}/></button><button title="Reset map" aria-label="Reset map" onClick={()=>setZoom(1)}><LocateFixed size={18}/></button></div>
    {zone&&showAqi&&<div className="zone-popup"><button className="icon-button" aria-label="Close zone details" onClick={()=>setZone(null)}><X size={16}/></button><span className="eyebrow">SIMULATED MONITORING ZONE</span><h3>{zone.name}</h3><div><strong>{winter?zone.value:Math.round(zone.value*.5)}</strong><span>AQI (IN) · {aqiLabel(winter?zone.value:Math.round(zone.value*.5))}</span></div><p>Scenario data for the frontend demo.</p></div>}
    <div className="map-bottom"><div className="map-legend"><span>AQI (IN)</span><i className="legend-dot moderate"/> Moderate<i className="legend-dot poor"/> Poor<i className="legend-dot severe"/> Severe</div><span className="north-arrow">N <ArrowUpRight size={15}/></span></div>
    <div className="map-insight"><div className="insight-icon"><Leaf size={19}/></div><div><strong>{activeRide?'Your demo ride is in progress':winter?'A small detour. A little less exposure.':'A clearer day to be on the move.'}</strong><p>{winter?'Compare routes around the simulated winter hotspots.':'Typical-day scenario is on. All readings are simulated.'}</p></div><Wind className="insight-wind" size={26}/></div>
  </div>;
}
