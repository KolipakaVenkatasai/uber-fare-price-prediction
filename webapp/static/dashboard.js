const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n);
const P=['#06c167','#276ef1','#f5a623','#e5484d','#8e4ec6','#12a594','#d6409f','#6b7280'];
(async()=>{
  const s=await (await fetch('/api/stats')).json();
  document.getElementById('kpis').innerHTML=[['Trips analysed',s.total_rides.toLocaleString()],['Average fare','₹'+Math.round(s.avg_fare).toLocaleString('en-IN')],['Median fare','₹'+Math.round(s.median_fare).toLocaleString('en-IN')],['Average distance',s.avg_distance+' km']]
    .map(([a,b])=>`<div class="card kpi"><span>${a}</span><b>${b}</b></div>`).join('');
  Chart.defaults.font.family='Inter';Chart.defaults.color=css('--muted').trim()||'#888';
  const mk=(id,type,labels,data,o={})=>new Chart(document.getElementById(id),{type,data:{labels,datasets:[{data,backgroundColor:o.colors||P[1]+'bb',borderColor:o.border||P[1],borderRadius:6,tension:.35,fill:o.fill,pointRadius:o.pr??2}]},
    options:{plugins:{legend:{display:!!o.legend}},scales:o.noScale?{}:{y:{ticks:{callback:v=>(o.fmt??'₹')+v}}},...(o.opts||{})}});
  mk('c1','line',s.hourly.labels.map(h=>h+':00'),s.hourly.values,{border:P[0],fill:true,colors:P[0]+'33'});
  mk('c2','bar',s.weekly.labels,s.weekly.values);
  mk('c3','line',s.monthly.labels,s.monthly.values,{border:P[2],fill:true,colors:P[2]+'33'});
  new Chart(document.getElementById('c4'),{type:'scatter',data:{datasets:[{data:s.scatter,backgroundColor:P[1]+'55',pointRadius:2}]},
    options:{plugins:{legend:{display:false}},scales:{x:{title:{display:true,text:'km'}},y:{title:{display:true,text:'fare ₹'}}}}});
  mk('c5','bar',s.importance.labels,s.importance.values,{fmt:'',opts:{indexAxis:'y',scales:{}},noScale:true,colors:P[0]+'bb'});
  mk('c6','bar',s.models.labels,s.models.r2,{fmt:'',colors:[P[1]+'bb',P[0]+'bb'],opts:{scales:{y:{min:0,max:1}}},noScale:true});
  mk('c7','bar',s.dist_fare.labels,s.dist_fare.values,{colors:P[4]+'bb'});
  new Chart(document.getElementById('c8'),{type:'doughnut',data:{labels:s.passengers.labels.map(x=>x+' pax'),datasets:[{data:s.passengers.values,backgroundColor:P}]}});
  const m=L.map('heatmap').setView([17.4126,78.4071],11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap contributors',maxZoom:19}).addTo(m);
  L.heatLayer(s.heat,{radius:12,blur:14}).addTo(m);
})();
