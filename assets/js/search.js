(function(){
  var q=document.getElementById('q'),res=document.getElementById('res'),idx=null;
  if(!q||!res)return;
  function kor(n){if(!n)return '-';var e=Math.floor(n/1e8),m=Math.floor((n%1e8)/1e4),s=[];if(e)s.push(e+'억');if(m)s.push(m.toLocaleString('ko-KR')+'만');return (s.join(' ')||n.toLocaleString('ko-KR'))+'원';}
  function esc(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]});}
  function load(cb){if(idx)return cb();fetch('/assets/search_index.json').then(function(r){return r.json()}).then(function(j){idx=j;cb()}).catch(function(){res.innerHTML='<p class="note">검색 데이터를 불러오지 못했습니다.</p>'});}
  function run(){var t=q.value.trim().toLowerCase();if(t.length<1){res.innerHTML='';return;}
    var toks=t.split(/\s+/);var out=[];
    for(var i=0;i<idx.length&&out.length<12;i++){var r=idx[i],h=(r[1]+' '+r[2]+' '+r[3]).toLowerCase(),ok=true;for(var j=0;j<toks.length;j++){if(h.indexOf(toks[j])<0){ok=false;break}}if(ok)out.push(r);}
    res.innerHTML=out.length?out.map(function(r){return '<a class="item-card" href="/item/'+encodeURIComponent(r[0])+'/"><div class="ph">'+(r[6]?'<img src="'+esc(r[6])+'" loading="lazy" referrerpolicy="no-referrer" alt="" onerror="this.remove()">':'<div class="ph noimg">사진 없음</div>')+'</div><div class="ib"><b class="t">'+esc(r[1])+'</b><span class="u">'+esc(r[2])+' · '+esc(r[3]||'-')+'</span><span class="p">감정가 '+kor(r[5])+'</span><span class="p2">최저 '+kor(r[4])+'</span></div></a>'}).join(''):'<p class="note">검색 결과가 없습니다.</p>';}
  q.addEventListener('input',function(){load(run)});
})();
