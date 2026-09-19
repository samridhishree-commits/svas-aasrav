import {readFileSync} from 'node:fs';
const values=Object.fromEntries(readFileSync('.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>{const i=l.indexOf('=');return[l.slice(0,i).trim(),l.slice(i+1).trim()]}));
console.log(JSON.stringify({browser_key_configured:!!values.VITE_GOOGLE_MAPS_API_KEY,backend_url_configured:!!values.VITE_API_BASE_URL}));
