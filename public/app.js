(function(){
var esc=function(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})};
document.querySelectorAll('time.ko').forEach(function(t){var d=new Date(t.getAttribute('datetime'));if(isNaN(d))return;
if(t.hasAttribute('data-full')){t.textContent=d.toLocaleString(undefined,{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}
else{t.innerHTML=d.toLocaleDateString(undefined,{weekday:'short',day:'numeric'})+'<br>'+d.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});}});
var q=document.getElementById('q');
if(q){var out=document.getElementById('res'),idx=[];
function show(v){v=v.trim().toLowerCase();var r=idx.filter(function(x){return !v||x.t.toLowerCase().indexOf(v)>-1}).slice(0,40);
out.innerHTML=r.map(function(x){return '<a class="ro" href="'+esc(x.u)+'"><span>'+esc(x.t)+'</span><span class="mu">'+esc(x.k)+'</span></a>'}).join('')||'<p class="mu">Nothing found.</p>';}
fetch('/search.json').then(function(r){return r.json()}).then(function(j){idx=j;show(q.value)});
q.addEventListener('input',function(){show(q.value)});}
})();