'use strict';
const $ = id => document.getElementById(id);
let currentRun = null, pollTimer = null;
const terminal = new Set(['completed','rejected','failed','interrupted']);
const pct = x => x == null ? 'N/A' : (x*100).toFixed(2)+'%';
const num = x => x == null ? 'N/A' : Number(x).toFixed(3);
function element(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
async function api(path, options={}) {
  const response=await fetch(path,options);const body=await response.json();
  if(!response.ok){const detail=body.detail;throw new Error(Array.isArray(detail)?detail.map(e=>(e.loc||[]).join('.')+': '+e.msg).join('\n'):String(detail||response.statusText));}
  return body;
}
function requestBody(){return {query:$('query').value,symbols:$('symbols').value.split(',').map(s=>s.trim()).filter(Boolean),benchmark:$('benchmark').value,
  provider:$('provider').value,start:$('start').value,end:$('end').value,strategy:$('strategy').value,rebalance:$('rebalance').value,
  lookback:Number($('lookback').value),fast_window:Number($('fast').value),slow_window:Number($('slow').value),
  commission_bps:Number($('commission').value),slippage_bps:Number($('slippage').value),initial_capital:Number($('capital').value),
  holdout_fraction:Number($('holdout').value),annual_risk_free_rate:Number($('riskfree').value)};}
async function history(){const result=await api('/api/research?limit=15');$('history').replaceChildren();
  if(!result.runs.length)$('history').textContent='No runs yet.';
  for(const run of result.runs){const b=element('button',run.query);b.type='button';b.append(element('small',run.status.toUpperCase()+' | '+new Date(run.created_at).toLocaleString()));b.addEventListener('click',()=>watch(run.id));$('history').append(b);}}
function showEvents(events){$('events').textContent=events.map(e=>{
 const tool=e.detail.tool?' / '+e.detail.tool:'';const ms=e.detail.elapsed_ms!==undefined?' ('+e.detail.elapsed_ms+' ms)':'';
 return e.agent+' > '+e.kind+tool+ms;
}).join('\n')||'Queued. Waiting for a worker...';$('events').scrollTop=$('events').scrollHeight;
 const done=new Set(events.filter(e=>e.kind==='agent_end').map(e=>e.agent));
 const names=['planner','data_agent','quant_agent','risk_agent','critic_agent','report_agent'];
 Array.from($('pipeline').children).forEach((n,i)=>n.classList.toggle('done',done.has(names[i])));}
async function watch(id){clearTimeout(pollTimer);currentRun=id;$('completed').hidden=true;$('empty').hidden=true;$('run-error').textContent='';
 try{await poll(id);}catch(e){$('run-error').textContent=e.message;$('run-button').disabled=false;}}
async function poll(id){const [run,events]=await Promise.all([api('/api/research/'+id),api('/api/research/'+id+'/events')]);
 if(currentRun!==id)return;
 $('status').textContent=run.status.toUpperCase();showEvents(events.events);$('run-button').disabled=!terminal.has(run.status);
 if(terminal.has(run.status)){if(run.result)render(run);else{$('run-error').textContent=run.error||'Run did not complete.';$('empty').hidden=false;}await history();}
 else pollTimer=setTimeout(()=>poll(id).catch(e=>{$('run-error').textContent=e.message;$('run-button').disabled=false;}),1000);}
function table(id,headers,rows){const t=$(id);t.replaceChildren();const head=element('thead'),tr=element('tr');headers.forEach(h=>tr.append(element('th',h)));head.append(tr);t.append(head);const body=element('tbody');for(const row of rows){const r=element('tr');row.forEach(cell=>r.append(element('td',cell)));body.append(r);}t.append(body);}
function svgNode(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs||{}))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
function drawCurve(rows){const svg=$('equity-chart');svg.replaceChildren();if(rows.length<2)return;const all=rows.flatMap(r=>[r.equity,r.benchmark_equity]),min=Math.min(...all),max=Math.max(...all),span=Math.max(max-min,1),left=60,right=740,top=12,bottom=230;
 const x=i=>left+i/(rows.length-1)*(right-left),y=v=>bottom-(v-min)/span*(bottom-top);
 for(let i=0;i<=4;i++){const value=min+span*i/4,yy=y(value);svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,class:'chart-grid'}),svgNode('text',{x:3,y:yy+3,class:'chart-axis'},Math.round(value).toLocaleString()));}
 for(const[key,cls]of[['equity','chart-strategy'],['benchmark_equity','chart-benchmark']]){const points=rows.map((r,i)=>x(i)+','+y(r[key])).join(' ');svg.append(svgNode('polyline',{points,class:cls}));}
 svg.append(svgNode('text',{x:left,y:251,class:'chart-axis'},rows[0].date),svgNode('text',{x:right,y:251,class:'chart-axis','text-anchor':'end'},rows.at(-1).date));}
function render(run){const r=run.result,m=r.backtest.metrics,detail=r.backtest_detail;$('completed').hidden=false;$('empty').hidden=true;
 $('source-badge').textContent=r.data.metadata.provider==='demo'?'SYNTHETIC DATA':'YAHOO FINANCE';$('metric-cards').replaceChildren();
 for(const[label,key,formatter]of[['CAGR','cagr',pct],['Sharpe','sharpe',num],['Max drawdown','max_drawdown',pct],['Volatility','annualised_volatility',pct]]){
 const card=element('div',undefined,'metric-card');card.append(element('small',label),element('strong',formatter(m.strategy[key])),element('em','Benchmark '+formatter(m.benchmark[key])));$('metric-cards').append(card);}
 const t=r.telemetry;$('run-meta').textContent=r.plan.strategy+' | '+detail.evaluation_start+' to '+detail.evaluation_end+' | '+t.tool_calls+' tool calls | '+t.elapsed_seconds.toFixed(2)+'s | '+t.llm_usage.calls+' LLM responses';
 drawCurve(detail.curve);
 const assetRows=Object.entries(r.analysis.assets).map(([symbol,v])=>[symbol,pct(v.total_return),pct(v.cagr),pct(v.annualised_volatility),num(v.beta_to_benchmark)]);
 table('performance-table',['Series','Total return','CAGR','Volatility','Beta'],[
 ['Strategy holdout',pct(m.holdout.total_return),pct(m.holdout.cagr),pct(m.holdout.annualised_volatility),'--'],
 ['Benchmark holdout',pct(m.holdout_benchmark.total_return),pct(m.holdout_benchmark.cagr),pct(m.holdout_benchmark.annualised_volatility),'--'],...assetRows]);
 const correlation=r.analysis.correlation,names=Object.keys(correlation);table('correlation-table',['Symbol',...names],names.map(a=>[a,...names.map(b=>num(correlation[a][b]))]));
 $('checks').replaceChildren();for(const c of r.verification.checks){const item=element('div',undefined,'check');item.append(element('strong',c.passed?'PASS':'FAIL'),element('span',c.name),element('p',c.detail));$('checks').append(item);}
 $('downloads').replaceChildren();for(const[label,path]of[['Markdown report','report'],['Full JSON','export/json'],['Equity CSV','export/curve'],['Trades CSV','export/trades'],['Data snapshot','export/snapshot']]){const a=element('a',label);a.href='/api/research/'+run.id+'/'+path;$('downloads').append(a);}
 $('report').textContent=r.report;
}
$('research-form').addEventListener('submit',async e=>{e.preventDefault();$('form-error').textContent='';$('run-button').disabled=true;
 try{const result=await api('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody())});await history();await watch(result.id);}
 catch(error){$('form-error').textContent=error.message;$('run-button').disabled=false;}});
$('replay').addEventListener('click',async()=>{if(!currentRun)return;try{const r=await api('/api/research/'+currentRun+'/replay',{method:'POST'});await watch(r.id);}catch(e){$('run-error').textContent=e.message;}});
(async()=>{try{const health=await api('/api/health');$('runtime').textContent=health.agent_mode.toUpperCase()+' / '+health.workflow_engine;
 $('runtime-detail').textContent='Tools: '+health.tool_transport+(health.tool_transport==='mcp'?' ('+health.mcp_implementation+' stdio)':'');
 $('mode-notice').textContent=health.agent_mode==='demo'?'DEMO MODE: deterministic role policies; no LLM calls or API charges. The default dataset is synthetic. Live market data must be selected explicitly.':'LLM MODE: model-driven tool calls can incur provider charges. Structured experiment fields and deterministic financial checks remain binding. '+(health.llm_configured?'':'WARNING: model/key configuration is missing.');await history();}
 catch(e){$('runtime').textContent='Connection error';$('mode-notice').textContent=e.message;}})();
