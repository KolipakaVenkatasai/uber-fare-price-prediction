const CITY_VIEW={"Hyderabad":[17.4126,78.4071,12],"Visakhapatnam":[17.7231,83.3013,12]};
const PLACES={
 // ---- Hyderabad
 "Charminar (Hyderabad)":[17.3616,78.4747],"Hitech City (Hyderabad)":[17.4435,78.3772],"Gachibowli (Hyderabad)":[17.4401,78.3489],
 "Banjara Hills (Hyderabad)":[17.4156,78.4347],"Jubilee Hills (Hyderabad)":[17.4326,78.4071],"Secunderabad Station":[17.4337,78.5016],
 "Rajiv Gandhi Airport (Shamshabad)":[17.2403,78.4294],"Tank Bund / Hussain Sagar":[17.4239,78.4738],"Begumpet (Hyderabad)":[17.4399,78.4983],
 "Madhapur (Hyderabad)":[17.4486,78.3908],"Kukatpally (Hyderabad)":[17.4948,78.3996],"LB Nagar (Hyderabad)":[17.3457,78.5522],
 "Ameerpet (Hyderabad)":[17.4375,78.4483],"Nampally Station (Hyderabad)":[17.3918,78.4690],"Golconda Fort":[17.3833,78.4011],
 "Uppal (Hyderabad)":[17.4058,78.5591],"Financial District (Hyderabad)":[17.4175,78.3400],
 // ---- Visakhapatnam (Vizag)
 "RK Beach (Vizag)":[17.7146,83.3233],"Visakhapatnam Railway Station":[17.7219,83.2894],"Visakhapatnam Airport":[17.7211,83.2245],
 "MVP Colony (Vizag)":[17.7387,83.3322],"Gajuwaka (Vizag)":[17.6868,83.2093],"Madhurawada (Vizag)":[17.8041,83.3777],
 "Rushikonda Beach (Vizag)":[17.7825,83.3850],"Simhachalam Temple (Vizag)":[17.7662,83.2506],"Dwaraka Nagar (Vizag)":[17.7285,83.3043],
 "Jagadamba Junction (Vizag)":[17.7092,83.3009],"Kailasagiri (Vizag)":[17.7480,83.3420],"Siripuram (Vizag)":[17.7208,83.3123]};
const HYD=Object.keys(PLACES).filter(k=>PLACES[k][1]<80),VIZ=Object.keys(PLACES).filter(k=>PLACES[k][1]>80);
const $=id=>document.getElementById(id);
let pickup=null,drop=null,mode=null,pax=1,mA=null,mB=null,line=null,hChart=null;
const map=L.map('map').setView([17.4126,78.4071],12);
const OSM='https://tile.openstreetmap.org/{z}/{x}/{y}.png';
let tl=L.tileLayer(OSM,{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19}).addTo(map);
const darkMap=()=>{map.getContainer().classList.toggle('dark-tiles',document.documentElement.dataset.theme==='dark');};
darkMap();window.addEventListener('themechange',darkMap);
const icon=c=>L.divIcon({className:'',html:`<div class="pin ${c}"></div>`,iconSize:[30,30],iconAnchor:[15,30]});

for(const sel of [$('pickupSel'),$('dropSel')]){
  sel.innerHTML='<option value="">— Choose a place —</option>'+'<optgroup label="Hyderabad">'+HYD.map(k=>`<option>${k}</option>`).join('')+'</optgroup><optgroup label="Visakhapatnam (Vizag)">'+VIZ.map(k=>`<option>${k}</option>`).join('')+'</optgroup>';
}
const now=new Date();now.setMinutes(now.getMinutes()-now.getTimezoneOffset());$('when').value=now.toISOString().slice(0,16);

function setPoint(kind,lat,lng,name){
  const p={lat,lng,name:name||'Custom point'};
  if(kind==='a'){pickup=p;if(mA)map.removeLayer(mA);mA=L.marker([lat,lng],{icon:icon('a')}).addTo(map);$('pickupTxt').textContent=`${p.name} · ${lat.toFixed(4)}, ${lng.toFixed(4)}`;}
  else{drop=p;if(mB)map.removeLayer(mB);mB=L.marker([lat,lng],{icon:icon('b')}).addTo(map);$('dropTxt').textContent=`${p.name} · ${lat.toFixed(4)}, ${lng.toFixed(4)}`;}
  if(line)map.removeLayer(line);
  if(pickup&&drop){line=L.polyline([[pickup.lat,pickup.lng],[drop.lat,drop.lng]],{color:'#276ef1',weight:4,dashArray:'8 8'}).addTo(map);map.fitBounds(line.getBounds(),{padding:[60,60]});}
}
$('pickupSel').onchange=e=>{const c=PLACES[e.target.value];if(c){setPoint('a',c[0],c[1],e.target.value);if(!drop)map.setView(c,13);}};
$('dropSel').onchange=e=>{const c=PLACES[e.target.value];if(c)setPoint('b',c[0],c[1],e.target.value);};
document.querySelectorAll('[data-city]').forEach(b=>b.onclick=e=>{e.preventDefault();const v=CITY_VIEW[b.dataset.city];map.setView([v[0],v[1]],v[2]);});
function setMode(m){mode=m;$('pickBtn').classList.toggle('active',m==='a');$('dropBtn').classList.toggle('active',m==='b');
  $('hint').textContent=m?`Click the map to set the ${m==='a'?'pickup':'dropoff'} point`:'Choose locations from the lists, or click “Pick on map”.';map.getContainer().style.cursor=m?'crosshair':'';}
$('pickBtn').onclick=()=>setMode(mode==='a'?null:'a');
$('dropBtn').onclick=()=>setMode(mode==='b'?null:'b');
map.on('click',e=>{if(!mode)return;setPoint(mode,e.latlng.lat,e.latlng.lng,'Custom point');
  (mode==='a'?$('pickupSel'):$('dropSel')).value='';setMode(mode==='a'&&!drop?'b':null);});
$('plus').onclick=()=>{pax=Math.min(6,pax+1);$('pax').textContent=pax;};
$('minus').onclick=()=>{pax=Math.max(1,pax-1);$('pax').textContent=pax;};
$('swapBtn').onclick=e=>{e.preventDefault();if(!pickup||!drop)return;const a=pickup,b=drop;
  setPoint('a',b.lat,b.lng,b.name);setPoint('b',a.lat,a.lng,a.name);$('pickupSel').value=PLACES[b.name]?b.name:'';$('dropSel').value=PLACES[a.name]?a.name:'';};

function payload(){return{pickup_latitude:pickup.lat,pickup_longitude:pickup.lng,dropoff_latitude:drop.lat,dropoff_longitude:drop.lng,
  passenger_count:pax,datetime:$('when').value,pickup_name:pickup.name,dropoff_name:drop.name};}
function showErr(m){$('err').textContent=m;$('err').hidden=!m;}
function animate(el,to){const t0=performance.now();(function f(t){const k=Math.min(1,(t-t0)/700);el.textContent=Math.round(to*(1-Math.pow(1-k,3))).toLocaleString('en-IN');if(k<1)requestAnimationFrame(f);})(t0);}

$('goBtn').onclick=async()=>{
  showErr('');if(!pickup||!drop)return showErr('Please choose both pickup and dropoff locations.');
  const btn=$('goBtn');btn.disabled=true;btn.textContent='Calculating…';
  try{
    const body=JSON.stringify(payload()),h={'Content-Type':'application/json'};
    const r=await fetch('/api/predict',{method:'POST',headers:h,body});const d=await r.json();
    if(!r.ok)throw new Error(d.error);
    $('result').hidden=false;animate($('fare'),d.fare);
    $('range').textContent=`₹${Math.round(d.low).toLocaleString('en-IN')} – ₹${Math.round(d.high).toLocaleString('en-IN')}`;
    $('dist').textContent=`${d.distance_km} km (${d.distance_mi} mi)`;$('perkm').textContent=`₹${Math.round(d.per_km).toLocaleString('en-IN')}`;
    $('lin').textContent=`₹${Math.round(d.linear_fare).toLocaleString('en-IN')}`;$('whenTxt').textContent=`${d.features.weekday}, ${String(d.features.hour).padStart(2,'0')}:00`;
    const hr=await (await fetch('/api/hourly',{method:'POST',headers:h,body})).json();
    drawHourly(hr,d.features.hour);$('result').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){showErr(e.message||'Something went wrong.');}
  btn.disabled=false;btn.textContent='Estimate fare';
};
function drawHourly(d,cur){
  if(hChart)hChart.destroy();
  hChart=new Chart($('hourChart'),{type:'bar',data:{labels:d.hours.map(h=>h+':00'),datasets:[{data:d.fares,
    backgroundColor:d.hours.map(h=>h===cur?'#06c167':'rgba(39,110,241,.45)'),borderRadius:6}]},
    options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>'₹'+Math.round(c.parsed.y).toLocaleString('en-IN')}}},scales:{y:{ticks:{callback:v=>'₹'+v}}}}});
}

window.addEventListener('resize',()=>map.invalidateSize());setTimeout(()=>map.invalidateSize(),300);
