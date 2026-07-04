"""The cockpit -- one page for the whole of her: the god view, her stream, her art, a talk.

A tiny stdlib HTTP server that runs INSIDE the persistent runner (a daemon thread beside
the wheel and the sleep), bound to 127.0.0.1 only -- nothing leaves the machine. One
dashboard, four panels -- and the point of all of them is LEGIBILITY: every mechanism
underneath is drawn, so a viewer can SEE the machinery working, not take it on faith.

  GOD VIEW    the town, alive and legible: souls walk (tweened, not teleporting), wearing
              mood-coloured breathing halos; every bond is a living thread (gold trust /
              cold-red enmity) and a thread FLASHES the moment it warms -- relationships
              forming on camera; when a soul speaks, its words travel as arcs to the souls
              actually in earshot and hang as a bubble; births bloom, deaths ripple out
              under a rising dagger; the sky turns dawn->night and the season tints the
              field; a CHRONICLE narrates the last moments ("Mara -> Cael: ..."); and
              clicking any soul opens the INSPECTOR -- its real insides: mood, belly,
              stores, the grip, its genome dials, every bond with trust and wounds, its
              last memories with their provenance tags, and the raw line its own tiny
              grown mind is currently murmuring. Nothing on screen is decoration; every
              pixel is a read of real state.
  HER STREAM  the readings as she speaks them, with the season and the hour she feels.
  HER ART     the wandering pen, embedded live (the same animator page).
  A TALK      a light visit: your words reach a real mind (bond, appraisal, memory).
              Click any soul to speak with it; the full ritual is `python3 chat.py`.

Same process as her life, so the god view and the chat read the SAME mind and world the
wheel is turning -- guarded by the runner's mind-lock, never a second writer."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765

UI_VERSION = 10   # bump on any dashboard change: live pages reload themselves to match

DASH = r"""<!doctype html><meta charset='utf-8'><title>Santāna — the cockpit</title>
<style>
 :root{--ink:#dfe0ea;--dim:#7d7d92;--warm:#f0ead6;--edge:#22222c}
 *{box-sizing:border-box}
 body{background:#08080c;color:var(--ink);font-family:Georgia,serif;margin:0;
  height:100vh;display:grid;grid-template-rows:auto 1fr;gap:9px;padding:11px}
 #hdr{display:flex;gap:20px;align-items:baseline;padding:2px 6px}
 #hdr b{color:var(--warm);font-size:19px;letter-spacing:.5px}
 #hdr .who{color:var(--ink);font-size:13px;font-style:italic}
 #hdr .v{font-size:12px;color:var(--dim)}
 #hdr .clock{margin-left:auto;font-size:12px;color:#9a9ab0}
 #hdr .drift{color:#c07a4a;font-size:11px}
 #grid{display:grid;grid-template-columns:1.7fr 1fr;grid-template-rows:1fr 1fr;
  gap:9px;min-height:0}
 .panel{background:linear-gradient(#141419,#101015);border:1px solid var(--edge);
  border-radius:8px;padding:9px;overflow:hidden;display:flex;flex-direction:column;
  min-height:0;position:relative}
 .panel h3{margin:0 0 7px;font-size:10.5px;color:var(--dim);font-weight:normal;
  text-transform:uppercase;letter-spacing:1.6px}
 #town{grid-row:span 2;padding:0;border-color:#1c1c26}
 #town h3{position:absolute;top:9px;left:12px;z-index:2;margin:0;
  text-shadow:0 1px 3px #000}
 #mapwrap{position:relative;width:100%;height:100%}
 canvas{width:100%;height:100%;display:block;border-radius:8px}
 #legend{position:absolute;left:12px;top:26px;font-size:9.5px;color:#8a8aa0;
  z-index:2;line-height:1.65;text-shadow:0 1px 2px #000;pointer-events:none}
 #legend i{font-style:normal;display:inline-block;width:10px;height:10px;
  border-radius:3px;vertical-align:-1px;margin-right:4px}
 #chron{position:absolute;left:12px;bottom:10px;z-index:2;font-size:10.5px;
  line-height:1.7;pointer-events:none;text-shadow:0 1px 2px #000;max-width:55%}
 #hint{position:absolute;right:12px;bottom:10px;font-size:10px;color:#6a6a7c;z-index:2;
  text-shadow:0 1px 2px #000}
 #insp{position:absolute;right:10px;top:30px;width:252px;z-index:3;display:none;
  background:rgba(11,11,17,.94);border:1px solid #2a2a38;border-radius:8px;
  padding:10px 11px;font-size:11px;line-height:1.5;max-height:82%;overflow-y:auto}
 #insp h4{margin:0 0 2px;color:var(--warm);font-size:14px;font-weight:normal}
 #insp .sub{color:var(--dim);font-size:10px;margin-bottom:7px}
 #insp .sec{color:#9a9ab0;font-size:9px;text-transform:uppercase;letter-spacing:1.2px;
  margin:8px 0 3px}
 #insp .bar{background:#1c1c26;border-radius:3px;height:6px;margin:2px 0 5px;overflow:hidden}
 #insp .bar i{display:block;height:100%;border-radius:3px}
 #insp .b{display:flex;justify-content:space-between;font-size:10.5px}
 #insp .mem{margin-bottom:4px;color:#c9c9d8;font-size:10px}
 #insp .src{font-size:8px;padding:0 4px;border-radius:3px;margin-right:4px;
  text-transform:uppercase;letter-spacing:.5px}
 #insp .x{position:absolute;top:6px;right:9px;cursor:pointer;color:var(--dim);
  font-size:14px}
 #insp .stir{color:#a09ab8;font-style:italic;font-size:10px}
 #stream{overflow-y:auto;font-size:13px;line-height:1.55}
 #stream .r{margin-bottom:9px;color:#eaeaf2}
 #stream .m{color:var(--dim);font-size:10.5px}
 iframe{border:0;width:100%;height:100%;background:#0e0e12;border-radius:5px}
 #chat{display:flex;flex-direction:column}
 #log{flex:1;overflow-y:auto;font-size:13px;line-height:1.55;margin-bottom:7px}
 #log .you{color:#8fb0c8}#log .her{color:var(--warm);margin-bottom:9px}
 #row{display:flex;gap:6px}
 select,input,button{background:#0c0c11;border:1px solid var(--edge);color:var(--ink);
  padding:8px;border-radius:5px;font-family:Georgia,serif;font-size:12px}
 input{flex:1}button{cursor:pointer;background:#20202a}button:hover{background:#2a2a38}
 .note{font-size:10px;color:#565663;margin-top:5px}
 ::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:#26262e;border-radius:4px}
</style>
<div id=hdr><b>Santāna</b><span class=who id=who></span><span class=v id=vitals></span>
 <span class=clock id=clock></span><span class=drift id=drift></span>
 <span class=v title="if this number is missing or lower, your browser is showing a stale cached page">cockpit v10</span></div>
<div id=grid>
 <div class=panel id=town><h3>the town — a living map</h3>
  <div id=mapwrap><canvas id=map width=1000 height=660></canvas>
   <div id=legend>
    <i style=background:#e6b24a></i>trust thread (flash = warming now) &nbsp;
    <i style=background:#b0485a></i>enmity<br>
    halo = mood · arc = words reaching a hearer · ✦ birth · † death · click a soul to
    open its insides</div>
   <div id=chron></div>
   <div id=insp><span class=x onclick="closeInsp()">×</span><div id=insp_body></div></div>
   <div id=hint>click a soul — inspect it, talk to it</div></div></div>
 <div class=panel><h3>her stream — what she is saying, live</h3><div id=stream></div></div>
 <div class=panel><h3>her hand — drawing her state, live</h3><iframe src="/drawings/live.html"></iframe></div>
 <div class=panel id=chat><h3>a talk — <span id=tgt>with HER</span></h3>
  <div id=log></div>
  <div id=row><select id=who_sel><option value="her">SANTĀNA</option></select>
  <input id=say placeholder="say something..."/>
  <button onclick="send()">speak</button></div>
  <div class=note>click a soul on the map for a word aside — it lands in that soul's real
  memory and bond. voices are self-grown; the one you talk to borrows a clear voice.
  her full ritual is: python3 chat.py</div></div>
</div>
<script>
const cv=document.getElementById('map');
// willReadFrequently forces SOFTWARE rasterisation: the user's GPU driver was
// dropping the canvas context (brief blackouts, recovering since v5) -- a CPU-drawn
// canvas takes the driver out of the picture entirely. Flat shapes at 30fps cost
// the CPU almost nothing.
let g=cv.getContext('2d',{willReadFrequently:true});
cv.addEventListener('contextlost',e=>{e.preventDefault();});
cv.addEventListener('contextrestored',()=>{g=cv.getContext('2d',{willReadFrequently:true});});
const W=1000,H=660, OX=26,OY=40, SX=(W-52)/900, SY=(H-96)/600;
const souls=new Map();      // id -> {x,y,tx,ty,mood,stage,asleep,name,action,drift,bonds,bubble}
const pairTrust=new Map();  // "a|b" -> last trust, to catch bonds WARMING on camera
let fx=[], chron=[], sky={hour:.35,season:'spring',night:false}, lastEv=0, sel='her';
const ACT={work:'⚒ ',share:'❥ ',tend:'✚ ',hoard:'▾ '};
const stars=[]; for(let i=0;i<90;i++){let s=(i*2654435761)>>>0;
 stars.push({x:(s%1000),y:((s>>10)%520),r:.4+((s>>4)%10)/12});}
const wx=a=>a.x*SX+OX, wy=a=>a.y*SY+OY;
const esc=t=>(t||'').replace(/[<&]/g,c=>c==='<'?'&lt;':'&amp;');
function moodRGB(m){const w=(m+1)/2;
 return [Math.round(58+150*w),Math.round(88+66*w),Math.round(150-72*w)];}
function note(text,color){chron.push({text,color:color||'#a8a8c0',t0:performance.now()});
 chron=chron.slice(-6);
 document.getElementById('chron').innerHTML=chron.map((c,i)=>
  `<div style="color:${c.color};opacity:${0.35+0.65*(i+1)/chron.length}">${esc(c.text)}</div>`).join('');}

function setTarget(id,name){sel=id;document.getElementById('who_sel').value=id;
 document.getElementById('tgt').textContent=id==='her'?'with HER':'aside with '+name;
 if(id!=='her')openInsp(id); else closeInsp();}
function closeInsp(){document.getElementById('insp').style.display='none';inspId=null;}
let inspId=null;
async function openInsp(id){inspId=id;
 document.getElementById('insp').style.display='block';refreshInsp();}
async function refreshInsp(){if(!inspId)return;
 try{const d=await(await fetch('/soul?id='+encodeURIComponent(inspId))).json();
  if(!d||!d.name)return;
  const bar=(v,c)=>`<div class=bar><i style="width:${Math.round(100*Math.max(0,Math.min(1,v)))}%;background:${c}"></i></div>`;
  const srcCol={self:'#3a4a6a',heard:'#5a4a2a',dream:'#4a3a5a',user:'#2a4a3a',
   event:'#333340',ai:'#3a4a6a',doctrine:'#40333a'};
  let h=`<h4>${esc(d.name)}</h4><div class=sub>${esc(d.role||'villager')} · ${d.stage} · `
   +`${d.age}/${d.lifespan} ticks lived</div>`;
  h+=`<div class=b><span>mood (felt)</span><span>${d.mood>0?'+':''}${d.mood}</span></div>`
   +bar((d.mood+1)/2,'linear-gradient(90deg,#4a5a8a,#e0c080)');
  h+=`<div class=b><span>wellbeing</span><span>${d.wellbeing}</span></div>`+bar(d.wellbeing,'#7aa07a');
  if(d.met!=null)h+=`<div class=b><span>belly (met)</span><span>${d.met}</span></div>`+bar(d.met,'#c0925a');
  h+=`<div class=b><span>stores</span><span>${d.stores}</span></div>`+bar(d.stores/1.5,'#8a8a5a');
  if(d.grip!=null&&d.grip>0.01)h+=`<div class=b><span>the grip</span><span>${d.grip}</span></div>`+bar(d.grip,'#a05a5a');
  if(d.genome){h+=`<div class=sec>genome (heritable)</div><div style="font-size:10px;color:#9a9ab0">`
   +Object.entries(d.genome).map(([k,v])=>`${k} ${v}`).join(' · ')+`</div>`;}
  if(d.bonds&&d.bonds.length){h+=`<div class=sec>bonds — who this soul holds</div>`;
   for(const b of d.bonds){const c=b.trust>=0?'#e6b24a':'#b0485a';
    h+=`<div class=b><span>${esc(b.name)}${b.wounds?` <span style="color:#b0485a">✗${b.wounds}</span>`:''}</span>`
     +`<span style="color:${c}">${b.trust>0?'+':''}${b.trust}</span></div>`;}}
  if(d.stir)h+=`<div class=sec>its tiny grown mind, right now</div><div class=stir>“${esc(d.stir)}”</div>`;
  if(d.memories&&d.memories.length){h+=`<div class=sec>last memories — with provenance</div>`;
   for(const m of d.memories){h+=`<div class=mem><span class=src style="background:${srcCol[m.source]||'#333340'}">`
    +`${esc(m.source)}</span>${esc(m.text)}</div>`;}}
  document.getElementById('insp_body').innerHTML=h;
 }catch(e){}}
setInterval(refreshInsp,3000);

document.getElementById('mapwrap').addEventListener('click',e=>{
 if(e.target.closest('#insp'))return;
 const r=cv.getBoundingClientRect();
 const px=(e.clientX-r.left)*W/r.width, py=(e.clientY-r.top)*H/r.height;
 let best=null,bd=30;
 for(const[id,d]of souls){const dd=Math.hypot(d.x-px,d.y-py);if(dd<bd){bd=dd;best=[id,d.name];}}
 if(best)setTarget(best[0],best[1]);});
document.getElementById('who_sel').addEventListener('change',e=>{
 const o=e.target.selectedOptions[0];setTarget(o.value,o.textContent);});

const MY_VERSION=10;
async function poll(){try{
 const s=await(await fetch('/state2')).json();
 // a page older than the server RELOADS ITSELF -- stale tabs were the source of a
 // whole evening of unreproducible "it goes dark" reports; never again
 if(s.ui_version&&s.ui_version>MY_VERSION){location.reload();return;}
 document.getElementById('who').textContent=s.identity||'a new mind';
 document.getElementById('vitals').textContent=
  `${s.age} · ${s.souls.length} souls · ${s.deaths} watched pass`;
 document.getElementById('clock').textContent=s.time_clause||'';
 document.getElementById('drift').textContent=(s.drift||[]).join('   ');
 document.getElementById('stream').innerHTML=
  s.readings.map(r=>`<div class=r>${esc(r.text)}<div class=m>${esc(r.meta)}</div></div>`).join('');
 sky={hour:s.hour,season:s.season,night:s.night};
 const live=new Set();
 for(const a of s.souls){live.add(a.id);
  let d=souls.get(a.id);
  if(!d){d={x:wx(a),y:wy(a)};souls.set(a.id,d);}
  d.tx=wx(a);d.ty=wy(a);d.mood=a.mood;d.stage=a.stage;d.asleep=a.asleep;
  d.name=a.name;d.action=a.action;d.drift=a.drift;d.bonds=a.bonds;}
 for(const[id,d]of souls) if(!live.has(id)&&!d.dying){d.dying=performance.now();}
 // bonds WARMING on camera: any pair whose trust rose since last poll flashes
 for(const a of s.souls)for(const[oid,tr]of(a.bonds||[])){
  const k=a.id<oid?a.id+'|'+oid:oid+'|'+a.id, prev=pairTrust.get(k);
  if(prev!=null&&tr>prev+0.004)fx.push({k:'warm',a:a.id,b:oid,t0:performance.now()});
  pairTrust.set(k,tr);}
 // events -> animation + chronicle, each exactly once
 for(const e of (s.events||[])){if(e.id<=lastEv)continue;lastEv=e.id;
  const d=souls.get(e.who); const nm=d?d.name:'a soul';
  if(e.kind==='speak'&&d){
   d.bubble={text:e.text,t0:performance.now()};
   for(const hid of (e.to||[]))if(souls.has(hid))
    fx.push({k:'arc',a:e.who,b:hid,t0:performance.now()});
   const hearers=(e.to||[]).map(h=>souls.get(h)).filter(Boolean).map(h=>h.name);
   note(`${nm}${hearers.length?' → '+hearers.slice(0,3).join(', '):''}: “${e.text}”`,'#9ab0c8');}
  else if(e.kind==='death'&&d){fx.push({k:'death',x:d.x,y:d.y,t0:performance.now()});
   note(`† ${nm} has passed`,'#b0a0a8');}
  else if(e.kind==='birth'){if(d)fx.push({k:'birth',id:e.who,t0:performance.now()});
   note(`✦ a soul is born`,'#e0c080');}}
 const S=document.getElementById('who_sel');
 if(S.options.length!==s.souls.length+1){const cur=S.value;
  S.innerHTML='<option value="her">SANTĀNA</option>'+
   s.souls.map(a=>`<option value="${a.id}">${esc(a.name)}</option>`).join('');
  S.value=[...S.options].some(o=>o.value===cur)?cur:'her';}
}catch(e){document.getElementById('drift').textContent='ui: '+e;}}

function drawSky(){
 // v9: THERE IS NO VISUAL NIGHT. Four rounds of night-brightening still read as
 // "it goes dark" on the user's screen -- so the map's brightness is now CONSTANT
 // by construction, day and night, forever. Night still exists in the world
 // (souls sleep, labour pauses, minds train); it shows as INFORMATION -- the
 // header clock, 'asleep' labels, a moon in the corner -- never as darkness.
 const grd=g.createLinearGradient(0,0,0,H);
 grd.addColorStop(0,'rgb(26,40,64)');
 grd.addColorStop(1,'rgb(54,64,86)');
 g.fillStyle=grd;g.fillRect(0,0,W,H);
 const tint={spring:[90,150,90],summer:[210,180,80],harvest:[210,140,60],winter:[110,140,190]}[sky.season]||[120,120,140];
 g.fillStyle=`rgba(${tint[0]},${tint[1]},${tint[2]},0.05)`;g.fillRect(0,0,W,H);
 if(sky.night){g.fillStyle='rgba(220,222,240,0.85)';g.font='16px Georgia';
  g.fillText('☾',W-30,26);g.font='9.5px Georgia';g.fillStyle='rgba(170,175,200,0.9)';
  g.fillText('night — the town sleeps',W-150,40);}
}

function drawThreads(){
 g.lineCap='round';
 for(const[id,d]of souls){if(d.dying)continue;
  for(const[oid,tr]of (d.bonds||[])){const o=souls.get(oid);
   if(!o||o.dying)continue; if(id>oid)continue;
   const a=Math.min(0.5,Math.abs(tr)*0.6);
   if(tr>=0)g.strokeStyle=`rgba(230,178,74,${a})`;
   else g.strokeStyle=`rgba(176,72,90,${a*0.9})`;
   g.lineWidth=tr>=0?0.5+2.2*tr:0.5;
   g.beginPath();g.moveTo(d.x,d.y);g.lineTo(o.x,o.y);g.stroke();}}
}

function drawSouls(now){
 const label=souls.size<=140, breathe=0.5+0.5*Math.sin(now/900);
 for(const[id,d]of souls){
  let fade=1;
  if(d.dying){const e=(now-d.dying)/1400; if(e>=1){souls.delete(id);continue;} fade=1-e;}
  const[r,gg,b]=moodRGB(d.mood), night=sky.night&&d.asleep;
  const rad=d.stage==='child'?3.5:(d.stage==='elder'?6.5:5.5);
  // night does NOT dim the souls at all -- the sky's cool tint and the stars say
  // "night". Halos are two flat arcs, not radial gradients: 64 gradients x 60fps
  // is exactly the GPU load that provokes context loss on fragile drivers.
  const glow=15+(night?0:4*breathe);
  g.fillStyle=`rgba(${r},${gg},${b},${0.16*fade})`;
  g.beginPath();g.arc(d.x,d.y,glow*1.6,0,7);g.fill();
  g.fillStyle=`rgba(${r},${gg},${b},${0.22*fade})`;
  g.beginPath();g.arc(d.x,d.y,glow*0.85,0,7);g.fill();
  g.globalAlpha=fade;
  g.fillStyle=`rgb(${Math.min(255,r+40)},${Math.min(255,gg+40)},${Math.min(255,b+40)})`;
  g.beginPath();g.arc(d.x,d.y,rad,0,7);g.fill();
  if(d.stage==='elder'){g.strokeStyle=`rgba(200,200,215,${0.6*fade})`;g.lineWidth=1;
   g.beginPath();g.arc(d.x,d.y,rad+2.5,0,7);g.stroke();}
  if(id===sel){g.strokeStyle=`rgba(240,234,214,0.9)`;g.lineWidth=1.6;
   g.beginPath();g.arc(d.x,d.y,rad+5,0,7);g.stroke();}
  g.globalAlpha=1;
  if(label){
   g.fillStyle=`rgba(220,221,232,${0.85*fade})`;g.font='12px Georgia';
   g.fillText(d.name,d.x+rad+4,d.y+3);
   g.fillStyle=`rgba(125,125,146,${0.9*fade})`;g.font='9.5px Georgia';
   const act=night?'asleep':((ACT[d.action]||'')+(d.action||''));
   g.fillText(act,d.x+rad+4,d.y+14);
   if(d.drift&&!night){g.fillStyle=`rgba(150,150,168,${0.5*fade})`;
    g.font='italic 8px Georgia';g.fillText(d.drift,d.x-6,d.y-11);}
   // the spoken line hangs as a bubble while it is fresh
   if(d.bubble){const bp=(now-d.bubble.t0)/2600;
    if(bp>=1)d.bubble=null;
    else{const tx='“'+d.bubble.text+'”';g.font='11px Georgia';
     const tw=g.measureText(tx).width;
     g.fillStyle=`rgba(12,12,20,${0.75*(1-bp)})`;
     g.fillRect(d.x+8,d.y-34,tw+10,16);
     g.fillStyle=`rgba(205,220,238,${0.95*(1-bp)})`;
     g.fillText(tx,d.x+13,d.y-22);}}}
 }
}

function drawFx(now){
 fx=fx.filter(f=>{
  const e=now-f.t0;
  if(f.k==='arc'){const p=e/750;if(p>=1)return false;
   const A=souls.get(f.a),B=souls.get(f.b);if(!A||!B)return false;
   const mx=(A.x+B.x)/2,my=(A.y+B.y)/2-18;
   g.strokeStyle=`rgba(150,200,235,${0.32*(1-p)})`;g.lineWidth=1;
   g.beginPath();g.moveTo(A.x,A.y);g.quadraticCurveTo(mx,my,B.x,B.y);g.stroke();
   const t=p, ix=(1-t)*(1-t)*A.x+2*(1-t)*t*mx+t*t*B.x,
             iy=(1-t)*(1-t)*A.y+2*(1-t)*t*my+t*t*B.y;
   g.fillStyle=`rgba(190,225,250,${0.9*(1-p*0.5)})`;
   g.beginPath();g.arc(ix,iy,2.2,0,7);g.fill();return true;}
  if(f.k==='warm'){const p=e/1200;if(p>=1)return false;
   const A=souls.get(f.a),B=souls.get(f.b);if(!A||!B)return false;
   g.strokeStyle=`rgba(255,225,140,${0.7*(1-p)})`;g.lineWidth=2.6*(1-p)+0.6;
   g.beginPath();g.moveTo(A.x,A.y);g.lineTo(B.x,B.y);g.stroke();return true;}
  if(f.k==='speak'){return false;}
  if(f.k==='birth'){const p=e/1100;if(p>=1)return false;
   const d=souls.get(f.id);if(!d)return false;
   g.fillStyle=`rgba(245,225,160,${0.4*(1-p)})`;
   g.beginPath();g.arc(d.x,d.y,30*p,0,7);g.fill();return true;}
  if(f.k==='death'){const p=e/1500;if(p>=1)return false;
   g.strokeStyle=`rgba(150,150,170,${0.5*(1-p)})`;g.lineWidth=1.5;
   g.beginPath();g.arc(f.x,f.y,6+58*p,0,7);g.stroke();
   g.fillStyle=`rgba(190,190,205,${0.7*(1-p)})`;g.font='14px Georgia';
   g.fillText('†',f.x-4,f.y-10-24*p);return true;}
  return false;});
}

let beat=0,lastErr='',lastDraw=0;
function frame(now){
 // UNKILLABLE: re-schedule FIRST (an exception can never stop the loop), draw in a
 // try/catch, paint any error ONTO the canvas, and run at 30fps -- half the GPU
 // load, indistinguishable to the eye at this pace.
 requestAnimationFrame(frame);
 if(now-lastDraw<33)return; lastDraw=now;
 try{
  for(const[,d]of souls){d.x+=(d.tx-d.x)*0.10;d.y+=(d.ty-d.y)*0.10;}
  drawSky();drawThreads();drawSouls(now);drawFx(now);
 }catch(err){lastErr=String(err);}
 beat++;
 g.fillStyle='rgba(160,160,180,0.8)';g.font='10px monospace';
 g.fillText('beat '+beat+' · souls '+souls.size+' · hour '+(sky.hour??'?'),W-210,H-8);
 if(lastErr){g.fillStyle='#e08a8a';g.font='12px monospace';
  g.fillText('renderer error: '+lastErr.slice(0,90),14,H-24);}}

async function send(){
 const inp=document.getElementById('say');const t=inp.value.trim();if(!t)return;
 const target=sel, who=target==='her'?'SANTĀNA':
  document.getElementById('who_sel').selectedOptions[0].textContent;
 inp.value='';const log=document.getElementById('log');
 log.innerHTML+=`<div class=you>you: ${esc(t)}</div>`;
 const p=document.createElement('div');p.className='her';p.style.opacity='.45';
 p.textContent=who+' is thinking…';log.appendChild(p);log.scrollTop=1e9;
 try{const r=await(await fetch('/say',{method:'POST',
   body:JSON.stringify({text:t,target})})).json();
  p.style.opacity='1';p.textContent=`${r.name||''}: ${r.reply||'...'}`;}
 catch(e){p.textContent='(no answer)';}
 log.scrollTop=1e9;}
document.getElementById('say').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
setInterval(poll,1500);poll();requestAnimationFrame(frame);
</script>"""


def _clip(text: str, n: int) -> str:
    """Cut on a WORD boundary with a real ellipsis -- a mid-word chop turns even a
    good line into apparent gibberish ('can't fa'), and the bubbles/murmurs were
    full of exactly that."""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:-")
    return (cut if cut else text[:n]) + "…"


def snapshot(mind, world, readings: list, drift_notes: list, events: list) -> dict:
    """Everything the dashboard shows, in one read -- world fields under the world lock,
    her fields as plain reads (the mind-lock guards the WRITERS)."""
    from world import clock as _clock
    with world.lock:
        night = world.clock_enabled and _clock.is_night(world.tick, world.day_ticks)
        clause = (_clock.time_clause(world.tick, world.day_ticks)
                  if world.clock_enabled else "")
        hour = _clock.hour(world.tick, world.day_ticks) if world.clock_enabled else 0.35
        season = _clock.season(world.tick, world.day_ticks) if world.clock_enabled else "spring"
        ids = {a.id for a in world.agents}
        souls = []
        for a in world.agents:
            # the bonds this soul actually carries -> the threads on the map. Only the
            # meaningful ones, only to souls on screen, strongest first (capped).
            bonds = [[oid, round(b.trust, 2)] for oid, b in getattr(a, "bonds", {}).items()
                     if oid in ids and abs(b.trust) >= 0.10]
            bonds.sort(key=lambda t: -abs(t[1]))
            souls.append({
                "id": a.id, "name": a.name, "x": a.position[0], "y": a.position[1],
                "mood": round(a.felt_mood(), 3), "action": getattr(a, "_last_action", ""),
                "stage": (_clock.stage(a.age, a.lifespan) if world.clock_enabled else "adult"),
                "asleep": night, "bonds": bonds[:5],
                "drift": (_clip(a.thought.drift[-1], 38)
                          if getattr(a.thought, "drift", None) else ""),
            })
    secs = getattr(mind, "lifetime", 0.0)
    age = (f"{secs/86400:.1f} days" if secs >= 86400 else f"{secs/3600:.1f} hours")
    return {"identity": (mind.identity or "")[:160], "age": age,
            "deaths": mind._deaths, "memories": len(mind.memory.items),
            "time_clause": clause, "night": night, "hour": round(hour, 3), "season": season,
            "souls": souls, "readings": readings[-10:][::-1], "drift": drift_notes[-3:],
            "events": list(events), "ui_version": UI_VERSION}


def soul_detail(world, sid: str) -> dict | None:
    """The INSPECTOR's read: one soul's actual insides -- state, genome, bonds with
    names, last memories WITH their provenance tags, and its grown mind's current
    murmur. Everything shown is a field that exists; nothing is synthesized."""
    from world import clock as _clock
    with world.lock:
        a = next((x for x in world.agents if x.id == sid), None)
        if a is None:
            return None
        names = {x.id: x.name for x in world.agents}
        gn = getattr(a, "genome", None)
        genome = None
        if gn is not None:
            genome = {k: round(v, 2) for k, v in (
                ("grip", getattr(gn, "grip", None)),
                ("compassion", getattr(gn, "compassion", None)),
                ("metabolism", getattr(gn, "metabolism", None)),
                ("boldness", getattr(gn, "boldness", None)),
            ) if isinstance(v, (int, float))}
        bonds = [{"name": names.get(oid, "one now gone"), "trust": round(b.trust, 2),
                  "wounds": b.wounds}
                 for oid, b in getattr(a, "bonds", {}).items()
                 if abs(b.trust) >= 0.05 or b.wounds]
        bonds.sort(key=lambda b: -abs(b["trust"]))
        mems = [{"text": m.text[:92], "source": m.source,
                 "emotion": round(getattr(m, "emotion", 0.0), 2)}
                for m in list(a.memory.items)[-8:]][::-1]
        met = getattr(a, "_met", None)
        return {
            "id": a.id, "name": a.name, "role": getattr(a, "role", ""),
            "stage": (_clock.stage(a.age, a.lifespan) if world.clock_enabled else "adult"),
            "age": a.age, "lifespan": a.lifespan,
            "mood": round(a.felt_mood(), 2), "wellbeing": round(a.wellbeing, 2),
            "stores": round(getattr(a, "stores", 0.0), 2),
            "met": round(met, 2) if isinstance(met, (int, float)) else None,
            "grip": round(getattr(a, "grip", 0.0), 2),
            "genome": genome, "bonds": bonds[:7], "memories": mems,
            "stir": (a.thought.drift[-1][:90] if getattr(a.thought, "drift", None) else ""),
        }


class _Handler(BaseHTTPRequestHandler):
    ui = None   # set by serve()

    def log_message(self, *_a):   # quiet: the runner's own log is the log
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # no-store: the dashboard evolves fast, and a browser quietly serving last
        # week's page made "it went dark" bugs unreproducible -- never cache the cockpit
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = self.ui
        if self.path in ("/", "/index.html"):
            self._send(DASH.encode(), "text/html; charset=utf-8")
        elif self.path.startswith("/state2"):
            with u["ev_lock"]:
                events = list(u["events"])
            snap = snapshot(u["mind"], u["world"], u["readings"], u["drift"], events)
            self._send(json.dumps(snap).encode(), "application/json")
        elif self.path.startswith("/state"):
            # THE GHOST-TAB DISABLER. Every dashboard before v8 polls THIS route and
            # renders whatever it gets with that morning's code -- including the
            # original pitch-black night that haunted an entire evening as an
            # unreproducible bug. Old tabs now receive an empty, bright, clearly
            # labelled world: no souls to hide, no night to darken, and a message
            # in their own stream panel telling the viewer to close them.
            stale = {"identity": "(this tab is OUTDATED -- close it and reopen the page)",
                     "age": "", "deaths": 0, "memories": 0,
                     "time_clause": "stale tab -- close me", "night": False,
                     "hour": 0.4, "season": "spring", "souls": [],
                     "readings": [{"text": "⚠ this tab is running an old cockpit page. "
                                           "Close this tab and open the address again "
                                           "-- the live town is waiting there.",
                                   "meta": "stale tab"}],
                     "drift": ["stale tab"], "events": [], "ui_version": UI_VERSION}
            self._send(json.dumps(stale).encode(), "application/json")
        elif self.path.startswith("/soul"):
            from urllib.parse import parse_qs, urlparse
            sid = (parse_qs(urlparse(self.path).query).get("id") or [""])[0]
            d = soul_detail(u["world"], sid)
            if d is None:
                self._send(b"{}", "application/json", 404)
            else:
                self._send(json.dumps(d).encode(), "application/json")
        elif self.path.startswith("/drawings/"):
            import os
            name = os.path.basename(self.path.split("?")[0])   # no traversal: basename only
            path = os.path.join(u["draw_dir"], name)
            if os.path.isfile(path):
                ctype = ("text/html" if name.endswith(".html") else
                         "image/svg+xml" if name.endswith(".svg") else
                         "application/javascript" if name.endswith(".js") else "text/plain")
                with open(path, "rb") as f:
                    self._send(f.read(), ctype)
            else:
                self._send(b"not yet -- she has not drawn here", "text/plain", 404)
        else:
            self._send(b"?", "text/plain", 404)

    def do_POST(self):
        u = self.ui
        if self.path != "/say":
            self._send(b"?", "text/plain", 404)
            return
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(n).decode())
            text = body["text"].strip()[:400]
            target = body.get("target", "her")
        except Exception:   # noqa: BLE001
            self._send(b'{"reply": null}', "application/json", 400)
            return
        chat_voice = u.get("chat_voice")         # the clear local voice (gemma), if up
        if target in ("her", "", None):
            with u["mind_lock"]:                 # one writer at a time, always
                mind = u["mind"]
                if chat_voice is not None:
                    # the cockpit talk borrows the clear voice for HER too (the talk
                    # tool always did); her memory, bond, appraisal are untouched --
                    # only the mouth changes for the length of one reply. If her own
                    # voice is the HOMEGROWN mind, it stays in the loop as the inner
                    # impulse the clear voice interprets (translation, not ghostwriting).
                    impulse = ""
                    if "Homegrown" in type(mind.llm).__name__:
                        try:
                            raw = mind.llm.generate(text, num_predict=60, temperature=0.9)
                            impulse = " ".join(str(raw).split())[:120]
                        except Exception:   # noqa: BLE001 -- a silent small mind is fine
                            pass
                    old_llm, mind.llm = mind.llm, chat_voice
                    try:
                        reply = mind.converse(text, inner_impulse=impulse)
                    finally:
                        mind.llm = old_llm
                else:
                    reply = mind.converse(text)
            self._send(json.dumps({"reply": reply, "name": "SANTĀNA"}).encode(),
                       "application/json")
            return
        # a quiet word aside with ONE soul: your words land in its real memory and
        # bond (hear with source='user'), its reply comes to you alone -- no town
        # broadcast. Prepare under the world lock, speak outside it (the contract).
        from world.events import Utterance
        world = u["world"]
        with world.lock:
            soul = next((a for a in world.agents if a.id == target), None)
            if soul is None:
                self._send(b'{"reply": null}', "application/json", 404)
                return
            soul.hear(Utterance(speaker_id="user", text=text, tick=world.tick,
                                addressed_to=soul.id, source="user"), world.tick,
                      speaker_name="a visitor")
            soul.last_heard_from, soul.last_heard_name = "user", "the visitor"
            soul.last_heard_text = text
            ctx, _addr, _mood = soul.prepare_speech()
        # THE ASIDE IS A DIALOGUE, not town speech. Reusing the ambient prompt made
        # souls chat past the visitor about harvests (the user caught it). An aside
        # builds its own conversational prompt: speak TO the visitor, hold THIS
        # thread, from the soul's real state -- persona, mood, its memories OF the
        # visitor, the bond -- with the grown mind's raw stirring as subtext (the
        # interpreter pattern; translation, never ghostwriting).
        own = ""
        if chat_voice is not None:
            try:
                own = " ".join(str(soul.llm.speak(ctx)).split())[:120]
                if own:
                    print(f"  (aside: {soul.name}'s grown mind stirred: {own[:70]!r} "
                          "-- the clear voice interprets it)", flush=True)
            except Exception:   # noqa: BLE001 -- a silent small mind is fine
                pass
        from services.prompts import _clean, _mood_word
        trail = u.setdefault("aside_trails", {}).setdefault(soul.id, [])
        if chat_voice is None:
            raw = ""
            try:
                raw = soul.llm.speak(ctx)        # no clear voice: the self-grown one, honestly
            except Exception:   # noqa: BLE001
                pass
        else:
            with world.lock:
                of_you = [m.text for m in soul.memory.items
                          if m.source == "user"][-5:-1]
                bond = soul.bonds.get("user")
                mood = _mood_word(soul.felt_mood())
                persona = getattr(soul, "persona", f"You are {soul.name}.")
            rel = ""
            if bond is not None and bond.history > 0.3:
                rel = ("You have come to trust this visitor." if bond.trust > 0.25 else
                       "This visitor has hurt you before -- be guarded." if bond.wounds
                       else "You are still taking this visitor's measure.")
            system = (f"{persona} You are standing in your small town, in a quiet private "
                      "conversation with a visitor who is HERE, before you. Speak directly "
                      "TO THEM -- second person, plain speech, one to three sentences, in "
                      "character. Never narrate, never address anyone else.")
            prompt = (f"You feel {mood}.\n"
                      + (f"{rel}\n" if rel else "")
                      + ("They have said to you before: " + "; ".join(of_you) + "\n"
                         if of_you else "")
                      + (("The conversation so far:\n" + "\n".join(trail[-6:]) + "\n")
                         if trail else "")
                      + (f"(A wordless stirring rises in you: \"{own}\" -- half-formed, "
                         "yours. Let whatever images live in it color your reply; never "
                         "quote its broken words.)\n" if own else "")
                      + f'\nThe visitor says to you: "{text}"\n\nAnswer the visitor.')
            raw = ""
            try:
                raw = chat_voice.generate(prompt, system=system, num_predict=90,
                                          temperature=0.7)   # 1-3 sentences: fewer
                                                             # tokens = faster replies
            except Exception:   # noqa: BLE001 -- a slow voice is a shrug, not a crash
                pass
        reply = _clean(raw) or "..."
        if reply != "...":
            # the soul REMEMBERS its own side of the talk (source=self, like any spoken
            # line) -- so the inspector shows both halves, and tonight's sleep trains on
            # the whole exchange, not just the visitor's words. Honest note: interpreted
            # replies are clear-voice English entering a self-grown mind's corpus; that
            # is the same doorway the visitor's own words already opened, and provenance
            # keeps every line auditable.
            with world.lock:
                soul.memory.write(reply[:160], tick=world.tick, source="self",
                                  speaker_id=soul.id)
        trail.append(f'visitor: "{text}"')
        trail.append(f'{soul.name}: "{reply}"')
        del trail[:-12]
        self._send(json.dumps({"reply": reply, "name": soul.name}).encode(),
                   "application/json")


def _wire_events(world, events: list, ev_lock, seq: list) -> None:
    """Subscribe to the world's bus so the map can ANIMATE what happens: speech arcs
    to the souls actually in earshot, birth blooms, death ripples. A tiny ring (bus
    fires on the wheel thread WHILE the world lock is held, so hooks read positions
    directly and must never re-acquire the lock). Every event gets a rising id so
    the client animates each exactly once; a failing hook never touches the wheel."""
    def on_speech(u):
        who = getattr(u, "speaker_id", "")
        if not who or who.startswith("mind:") or who == "user":
            return
        text = _clip(getattr(u, "text", "") or "", 96)
        hearers = []
        try:
            spk = next((a for a in world.agents if a.id == who), None)
            if spk is not None:
                reach = world.hearing_range * 2.0
                hearers = [b.id for b in world.agents
                           if b is not spk and world._distance(b, spk) <= reach][:8]
        except Exception:   # noqa: BLE001 -- a hook must never hurt the wheel
            pass
        with ev_lock:
            seq[0] += 1
            events.append({"id": seq[0], "kind": "speak", "who": who,
                           "text": text, "to": hearers})
            del events[:-80]

    def record(kind):
        def hook(payload):
            who = payload if isinstance(payload, str) else getattr(payload, "id", "")
            if not who:
                return
            with ev_lock:
                seq[0] += 1
                events.append({"id": seq[0], "kind": kind, "who": who})
                del events[:-80]
        return hook

    world.bus.subscribe("utterance", on_speech)
    world.bus.subscribe("death", record("death"))
    world.bus.subscribe("starvation", record("death"))
    world.bus.subscribe("birth", record("birth"))
    world.bus.subscribe("rebirth", record("birth"))


def serve(mind, world, mind_lock, draw_dir: str, readings: list, drift_notes: list,
          port: int = PORT, chat_voice=None):
    """Start the cockpit (daemon thread, 127.0.0.1 only). Returns the URL.
    chat_voice: an optional CLEAR local voice (e.g. gemma via ollama) that the talk
    panel borrows -- for her and for asides -- while the ambient town keeps its own."""
    events: list = []
    ev_lock = threading.Lock()
    _wire_events(world, events, ev_lock, [0])
    _Handler.ui = {"mind": mind, "world": world, "mind_lock": mind_lock,
                   "draw_dir": draw_dir, "readings": readings, "drift": drift_notes,
                   "chat_voice": chat_voice, "events": events, "ev_lock": ev_lock}
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"
