/* Tiny NETWORK-FIRST service worker for /draft2/: makes the room installable, never serves stale files while online.
   Every same-origin GET goes to the network with cache:'no-store' (so GitHub Pages' 10-minute HTTP cache cannot hold back a fix);
   the cached copy is only a fallback when the phone is offline. textdb (cross-origin) is never touched.
   v4: bumped for the Party Paul -> Paul owner rename (forces the new index.html on installed copies; activate deletes every older stoopids-draft2-* cache).
   v3: bumped for the Poo -> Party Paul owner rename.
   v2: new cache name; on activate it removes older draft2 caches AND any /draft2/ file the v1 worker stored in the shared
   'stoopids-draft-v1' cache, so the previously shipped (broken) index.html can never be served again, even offline. */
const CACHE='stoopids-draft2-v4';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{
  for(const k of await caches.keys())if(k.startsWith('stoopids-draft2-')&&k!==CACHE)await caches.delete(k);   // never touch the /draft/ room's cache
  try{const old=await caches.open('stoopids-draft-v1');for(const r of await old.keys())if(new URL(r.url).pathname.indexOf('/draft2/')>=0)await old.delete(r)}catch(_){}
  await self.clients.claim()})())});
self.addEventListener('fetch',e=>{
  const r=e.request;
  if(r.method!=='GET'||new URL(r.url).origin!==self.location.origin)return;   // textdb etc. always go straight to the network
  e.respondWith(fetch(r,{cache:'no-store'}).then(res=>{if(res&&res.ok){const c=res.clone();caches.open(CACHE).then(ch=>ch.put(r,c)).catch(()=>{})}return res}).catch(()=>caches.match(r,{ignoreSearch:true})))});
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(l=>{for(const c of l){if('focus' in c)return c.focus()}return self.clients.openWindow('./')}))});
