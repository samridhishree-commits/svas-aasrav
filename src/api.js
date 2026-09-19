const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status = 0, code = 'NETWORK_ERROR') { super(message); this.status=status; this.code=code; }
}

async function request(path, { signal, timeout = 90000, ...options } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once:true });
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...options, headers:{'Content-Type':'application/json',...options.headers}, signal:controller.signal,
    });
    let data;
    try { data = await response.json(); } catch { throw new ApiError('The API returned an unreadable response.', response.status); }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(d=>d.msg).join(' ') : data.detail;
      throw new ApiError(detail || 'The request could not be completed.', response.status, data.code);
    }
    return data;
  } catch(error) {
    if (signal?.aborted) throw new DOMException('Request cancelled','AbortError');
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError('The request timed out. Please try again.', 0, 'TIMEOUT');
    throw new ApiError('Cannot reach the API. Start FastAPI on port 8000, or check the configured backend address.');
  } finally { clearTimeout(timer); signal?.removeEventListener('abort',abort); }
}

export const getCityAqi = (signal) => request('/api/city-aqi', {signal,timeout:35000});
export const calculateRoute = (payload, signal) => request('/api/calculate-route', { method:'POST',body:JSON.stringify(payload),signal });
export const getGraphSummary = (signal) => request('/api/graph-summary',{signal,timeout:30000});
export const getHealth = (signal) => request('/api/health',{signal,timeout:10000});
export const parseTrip = (payload,signal) => request('/api/ai/parse-trip',{method:'POST',body:JSON.stringify(payload),signal,timeout:45000});
export const analyzeExposure = (tripId,routeId,signal) => request('/api/ai/exposure-analysis',{method:'POST',body:JSON.stringify({trip_id:tripId,route_id:routeId}),signal,timeout:45000});

export function usAqiLabel(value) {
  if (!Number.isFinite(value)) return 'Unavailable';
  return value<=50?'Good':value<=100?'Moderate':value<=150?'Unhealthy for sensitive groups':value<=200?'Unhealthy':value<=300?'Very unhealthy':'Hazardous';
}

export const suggestFleet = (prompt,signal) => request('/api/ai/fleet-suggestions',{method:'POST',body:JSON.stringify({prompt}),signal,timeout:180000});
