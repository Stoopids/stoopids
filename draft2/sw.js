/* Tiny network-first service worker: makes the draft room installable, never serves stale files when online. */
const CACHE='stoopids-draft-v1';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{for(const k of await caches.keys())if(k!==CACHE)await caches.delete(k);await self.clients.claim()})())});
self.addEventListener('fetch',e=>{
  const r=e.request;
  if(r.method!=='GET'||new URL(r.url).origin!==self.location.origin)return;   // textdb etc. always go straight to the network
  e.respondWith(fetch(r,{cache:'no-store'}).then(res=>{if(res&&res.ok){const c=res.clone();caches.open(CACHE).then(ch=>ch.put(r,c)).catch(()=>{})}return res}).catch(()=>caches.match(r,{ignoreSearch:true})))});
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(l=>{for(const c of l){if('focus' in c)return c.focus()}return self.clients.openWindow('./')}))});
