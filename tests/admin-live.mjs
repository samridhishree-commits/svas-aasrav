import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
  await page.goto('http://localhost:5173');
  await page.getByRole('button',{name:'Admin',exact:true}).click();
  await page.getByRole('textbox',{name:'Describe your fleet request'}).fill('I have 5 unmasked riders at Saket. Route them to Rohini but absolutely avoid any zones with AQI over 300.');
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/ai/fleet-suggestions'),{timeout:180000});
  await page.getByRole('button',{name:'Suggest routes',exact:true}).click();
  const response=await pending;const data=await response.json();
  assert.equal(response.status(),200);assert.equal(data.status,'ready');assert.equal(data.scheduled,false);
  assert.equal(data.intent.rider_count,5);assert.equal(data.intent.payload.has_mask,false);
  await page.locator('.route-card').first().waitFor();
  assert.equal(await page.locator('.route-card').count(),data.comparison.routes.length);
  assert.equal(await page.getByRole('button',{name:/Schedule riders/}).isDisabled(),true);
  assert.ok(!/Neo4j|Gemini|OSRM|FastAPI|MapLibre/.test(await page.locator('body').innerText()));
  await page.screenshot({path:'artifacts/admin-advisor-live.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(400);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: live fleet intent, current route suggestions, disabled scheduling, clean product copy and mobile layout.');
}finally{await browser.close()}
