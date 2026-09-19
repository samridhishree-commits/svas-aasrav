export const locations = [
  { id: 'saket', name: 'Saket', detail: 'South Delhi, New Delhi', lat: 28.5245, lng: 77.2066, x: 590, y: 545 },
  { id: 'rohini', name: 'Rohini', detail: 'Sector 7, North West Delhi', lat: 28.7149, lng: 77.1164, x: 225, y: 125 },
  { id: 'cp', name: 'Connaught Place', detail: 'Central Delhi, New Delhi', lat: 28.6315, lng: 77.2167, x: 600, y: 315 },
  { id: 'dwarka', name: 'Dwarka', detail: 'Sector 12, South West Delhi', lat: 28.5921, lng: 77.046, x: 130, y: 460 },
  { id: 'janakpuri', name: 'Janakpuri', detail: 'West Delhi, New Delhi', lat: 28.6219, lng: 77.0878, x: 240, y: 345 },
  { id: 'noida', name: 'Noida', detail: 'Sector 18, Uttar Pradesh', lat: 28.5708, lng: 77.3261, x: 845, y: 490 },
  { id: 'karol', name: 'Karol Bagh', detail: 'Central Delhi, New Delhi', lat: 28.6514, lng: 77.1907, x: 470, y: 255 },
  { id: 'gurugram', name: 'Gurugram', detail: 'Cyber City, Haryana', lat: 28.4949, lng: 77.0888, x: 250, y: 575 },
];
export const zones = [
  { id: 'anand', name: 'Anand Vihar', value: 428, x: 810, y: 215, lat: 28.6469, lng: 77.316, radius: 70, kind: 'severe' },
  { id: 'wazir', name: 'Wazirpur', value: 386, x: 450, y: 155, lat: 28.699, lng: 77.166, radius: 67, kind: 'poor' },
  { id: 'punjabi', name: 'Punjabi Bagh', value: 312, x: 345, y: 285, lat: 28.668, lng: 77.133, radius: 53, kind: 'poor' },
  { id: 'lodhi', name: 'Lodhi Road', value: 168, x: 615, y: 422, lat: 28.591, lng: 77.227, radius: 55, kind: 'moderate' },
];
export function makeRoutes(origin, destination, winter = true) {
  const km = Math.hypot((origin.lat - destination.lat) * 111, (origin.lng - destination.lng) * 97) * 1.35;
  const base = Math.max(12, Math.round(km * 1.72));
  return [
    { id: 'clean', name: 'Breathe easy', tag: 'RECOMMENDED', via: 'via Outer Ring Road', minutes: base + 9, distance: (km + 3.8).toFixed(1), aqi: winter ? 186 : 112, severeMinutes: winter ? 3 : 0, color: '#277b58', exposure: 34 },
    { id: 'fast', name: 'The quick way', tag: 'FASTEST', via: 'via Ring Road', minutes: base, distance: km.toFixed(1), aqi: winter ? 324 : 156, severeMinutes: winter ? 16 : 0, color: '#8d99aa', exposure: 78 },
    { id: 'balanced', name: 'A little of both', tag: 'BALANCED', via: 'via Patel Road', minutes: base + 5, distance: (km + 1.9).toFixed(1), aqi: winter ? 242 : 134, severeMinutes: winter ? 8 : 0, color: '#b79b6d', exposure: 51 },
  ];
}
export function recommendRoute(routes, availableMinutes, mask) {
  const eligible = routes.filter(r => r.minutes <= availableMinutes && (mask || r.severeMinutes === 0));
  return [...eligible].sort((a,b) => a.aqi - b.aqi || a.minutes - b.minutes)[0] || null;
}
export function aqiLabel(value) { return value <= 50 ? 'Good' : value <= 100 ? 'Satisfactory' : value <= 200 ? 'Moderate' : value <= 300 ? 'Poor' : value <= 400 ? 'Very poor' : 'Severe'; }
export function routePoints(origin, destination, routeId) {
  const dx = destination.x - origin.x, dy = destination.y - origin.y;
  const bend = routeId === 'clean' ? -125 : routeId === 'balanced' ? -38 : 62;
  return [ [origin.x, origin.y], [origin.x - 30, origin.y - 35], [origin.x + dx * .3 + bend, origin.y + dy * .25], [origin.x + dx * .5 + bend, origin.y + dy * .52], [origin.x + dx * .8 + bend * .4, origin.y + dy * .76], [destination.x + 30, destination.y + 25], [destination.x,destination.y] ];
}
export const trips = [
  { id: 'BR-2048', from: 'Saket', to: 'Rohini', date: 'Today, 10:24 AM', time: '54 min', distance: '29.6 km', status: 'Completed', rider: 'Aarav Sharma', aqi: 186 },
  { id: 'BR-2047', from: 'Connaught Place', to: 'Dwarka', date: 'Yesterday, 3:15 PM', time: '42 min', distance: '23.4 km', status: 'Completed', rider: 'Priya Singh', aqi: 172 },
  { id: 'BR-2046', from: 'Janakpuri', to: 'Karol Bagh', date: 'Yesterday, 11:40 AM', time: '31 min', distance: '14.2 km', status: 'Completed', rider: 'Kabir Mehta', aqi: 204 },
];
