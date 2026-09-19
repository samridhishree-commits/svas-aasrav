import test from 'node:test';
import assert from 'node:assert/strict';
import { locations, makeRoutes, recommendRoute, aqiLabel } from '../src/data.js';

test('a recommendation meets the time window and favors lower AQI', () => {
  const routes = makeRoutes(locations[0], locations[1], true);
  const recommended = recommendRoute(routes, 90, true);
  assert.equal(recommended.id, 'clean');
  assert.ok(recommended.minutes <= 90);
});
test('an impossible deadline never returns an on-time recommendation', () => {
  assert.equal(recommendRoute(makeRoutes(locations[0], locations[1]), 1, true), null);
});
test('an unmasked rider is not recommended a route with severe-zone exposure', () => {
  assert.equal(recommendRoute(makeRoutes(locations[0], locations[1], true), 120, false), null);
  assert.equal(recommendRoute(makeRoutes(locations[0], locations[1], false), 120, false).severeMinutes, 0);
});
test('a tighter deadline can select a faster route when it is the only eligible one', () => {
  const routes = makeRoutes(locations[0], locations[1]);
  const fastest = routes.find(r => r.id === 'fast');
  assert.equal(recommendRoute(routes, fastest.minutes, true).id, 'fast');
});
test('AQI categories follow the Indian scale at boundaries', () => {
  assert.equal(aqiLabel(100), 'Satisfactory');
  assert.equal(aqiLabel(101), 'Moderate');
  assert.equal(aqiLabel(200), 'Moderate');
  assert.equal(aqiLabel(201), 'Poor');
  assert.equal(aqiLabel(400), 'Very poor');
  assert.equal(aqiLabel(401), 'Severe');
});
