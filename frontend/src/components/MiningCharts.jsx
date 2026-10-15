import React,{useEffect,useMemo,useState} from "react";
import {ScatterChart,Scatter,XAxis,YAxis,ZAxis,CartesianGrid,Tooltip,ResponsiveContainer,LineChart,Line,ReferenceDot,BarChart,Bar,Cell,Legend} from "recharts";
import {BarChart3} from "lucide-react";
import {Card,Title,Tip,PALETTE,fmtN} from "./ui.jsx";
import {getMiningKMeans,getMiningDBSCAN,getMiningApriori} from "../services/api";

const lonFmt=v=>Number(v).toFixed(2), latFmt=v=>Number(v).toFixed(2);
const cap=s=>s.toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());
export function pretty(item){
 return String(item).split(", ").map(x=>{const [k,...r]=x.split("_");const v=cap(r.join(" "));return k==="ARREST"?`Arrest: ${v}`:`${cap(k)}: ${v}`}).join(" + ");
}
function Stats({items}){return <div className="miniStats">{items.map(([l,v,s])=><div key={l}><span>{l}</span><b>{v}</b>{s&&<small>{s}</small>}</div>)}</div>}
function Loading({error}){return <div className="empty">{error||"Loading chart data…"}</div>}
function MiniBars({rows,labelKey,valueKey,fmt=v=>fmtN(v),color="#f97316",limit=10}){
 const a=rows.slice(0,limit),max=Math.max(...a.map(r=>r[valueKey]),1e-9);
 return <div className="bars">{a.map((r,i)=><div className="barRow" key={i}><span title={r[labelKey]}>{r[labelKey]}</span><div className="barBg"><div className="barFill" style={{width:`${r[valueKey]/max*100}%`,background:color}}/></div><b>{fmt(r[valueKey])}</b></div>)}</div>
}
const PointTip=({active,payload})=>{if(!active||!payload?.length)return null;const p=payload[0].payload;return <div className="chartTip"><b>{p.title||`Cluster ${p.cluster}`}</b><div>Lat {Number(p.Latitude).toFixed(4)}</div><div>Lon {Number(p.Longitude).toFixed(4)}</div>{p.size&&<div>{fmtN(p.size)} cases</div>}</div>};
const spatialAxes=<><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="Longitude" name="Longitude" domain={["dataMin","dataMax"]} tickFormatter={lonFmt} tick={{fontSize:10}} label={{value:"Longitude",position:"insideBottom",offset:-4,fontSize:11}} height={42}/><YAxis type="number" dataKey="Latitude" name="Latitude" domain={["dataMin","dataMax"]} tickFormatter={latFmt} tick={{fontSize:10}} width={46} label={{value:"Latitude",angle:-90,position:"insideLeft",fontSize:11}}/><ZAxis type="number" range={[16,16]}/></>;

/* ------------------------------------------------------------ K-MEANS */
export function KMeansPanel({d}){
 if(!d)return <Loading/>;
 const clusters=[...new Set(d.points.map(p=>p.cluster))].sort((a,b)=>a-b);
 const best=d.silhouette.find(s=>s.k===d.best_k);
 const centers=d.centers.map(c=>({...c,title:`Cluster ${c.cluster} centre`}));
 return <>
  <Stats items={[["Clusters (k)",d.sizes.length,"chosen by silhouette"],["Best silhouette",Number(best?.silhouette||0).toFixed(3),`at k = ${d.best_k}`],["Crime locations",fmtN(d.total),"clustered"],["Largest cluster",`${Math.max(...d.sizes.map(s=>s.share))}%`,"of all locations"]]}/>
  <div className="grid2eq">
   <Card><Title title="Hotspot clusters on the map" sub={`${fmtN(d.points.length)} sampled locations · ◆ = cluster centre`}/><div className="chart tall"><ResponsiveContainer><ScatterChart margin={{top:10,right:14,bottom:8,left:0}}>{spatialAxes}<ZAxis type="number" zAxisId="c" range={[220,220]}/><Tooltip content={<PointTip/>} cursor={{strokeDasharray:"3 3"}}/>
    {clusters.map((c,i)=><Scatter key={c} name={`Cluster ${c}`} data={d.points.filter(p=>p.cluster===c)} fill={PALETTE[i%PALETTE.length]} fillOpacity={.55} isAnimationActive={false}/>)}
    <Scatter name="Centres" data={centers} zAxisId="c" shape="diamond" fill="#111827" stroke="#fff" isAnimationActive={false}/></ScatterChart></ResponsiveContainer></div>
    <div className="legendRow">{clusters.map((c,i)=><span key={c}><i style={{background:PALETTE[i%PALETTE.length]}}/>Cluster {c}</span>)}<span><i className="diamond"/>Centre</span></div></Card>
   <div className="stackCol">
    <Card><Title title="How many clusters? (silhouette score)" sub="Higher = cleaner separation"/><div className="chart"><ResponsiveContainer><LineChart data={d.silhouette} margin={{top:14,right:16,bottom:6,left:0}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="k" tick={{fontSize:11}} label={{value:"Number of clusters (k)",position:"insideBottom",offset:-4,fontSize:11}} height={42}/><YAxis domain={["auto","auto"]} tick={{fontSize:10}} tickFormatter={v=>Number(v).toFixed(2)} width={42}/><Tooltip formatter={v=>Number(v).toFixed(3)} labelFormatter={k=>`k = ${k}`}/><Line type="monotone" dataKey="silhouette" name="Silhouette" stroke="#3b82f6" strokeWidth={3} dot={{r:4}} isAnimationActive={false}/>{best&&<ReferenceDot x={best.k} y={best.silhouette} r={8} fill="#f97316" stroke="#fff" strokeWidth={2} label={{value:"best",position:"top",fontSize:11,fill:"#f97316"}}/>}</LineChart></ResponsiveContainer></div></Card>
    <Card><Title title="Cluster sizes" sub="Share of crime locations"/><div className="splitBar">{d.sizes.map((s,i)=><div key={s.cluster} style={{width:`${s.share}%`,background:PALETTE[i%PALETTE.length]}} title={`Cluster ${s.cluster}: ${fmtN(s.size)}`}>{s.share>8&&`C${s.cluster} · ${s.share}%`}</div>)}</div></Card>
   </div>
  </div>
  <Tip>K-Means splits the city into k groups by location. Each ◆ is the centre of a group. The silhouette chart shows the k with the cleanest separation — here k = {d.best_k}, so the city divides into {d.best_k} broad crime zones.</Tip>
 </>
}

/* ------------------------------------------------------------ DBSCAN */
export function DBSCANPanel({d}){
 if(!d)return <Loading/>;
 const idx=Object.fromEntries(d.top_ids.map((id,i)=>[id,i]));
 const noise=d.points.filter(p=>p.cluster===-1),other=d.points.filter(p=>p.cluster!==-1&&!(p.cluster in idx));
 const bars=d.top_clusters.map((c,i)=>({name:`#${c.cluster}`,size:c.size,i}));
 return <>
  <Stats items={[["Dense clusters",d.n_clusters,"found automatically"],["Noise points",`${d.noise_share}%`,"not in any dense area"],["Largest cluster",fmtN(d.top_clusters[0]?.size||0),`cluster #${d.top_clusters[0]?.cluster}`],["Locations analysed",fmtN(d.total)]]}/>
  <div className="grid2eq">
   <Card><Title title="Dense crime zones" sub="Coloured = 15 largest clusters · grey = noise"/><div className="chart tall"><ResponsiveContainer><ScatterChart margin={{top:10,right:14,bottom:8,left:0}}>{spatialAxes}<Tooltip content={<PointTip/>} cursor={{strokeDasharray:"3 3"}}/>
    <Scatter name="Noise" data={noise} fill="#cbd5e1" fillOpacity={.55} isAnimationActive={false}/>
    <Scatter name="Smaller clusters" data={other} fill="#fdba74" fillOpacity={.7} isAnimationActive={false}/>
    {d.top_ids.map((id,i)=><Scatter key={id} name={`Cluster ${id}`} data={d.points.filter(p=>p.cluster===id)} fill={PALETTE[i%PALETTE.length]} fillOpacity={.8} isAnimationActive={false}/>)}</ScatterChart></ResponsiveContainer></div>
    <div className="legendRow"><span><i style={{background:"#cbd5e1"}}/>Noise</span><span><i style={{background:"#fdba74"}}/>Smaller clusters</span><span><i style={{background:"#f97316"}}/>Top-15 clusters (coloured)</span></div></Card>
   <Card><Title title="Biggest hotspots" sub="Cases per dense cluster"/><div className="chart tall"><ResponsiveContainer><BarChart data={bars} layout="vertical" margin={{top:6,right:24,bottom:6,left:4}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:10}}/><YAxis type="category" dataKey="name" width={40} tick={{fontSize:11}}/><Tooltip formatter={v=>[fmtN(v)+" cases","Size"]}/><Bar dataKey="size" radius={[0,5,5,0]} isAnimationActive={false}>{bars.map((b,i)=><Cell key={i} fill={PALETTE[i%PALETTE.length]}/>)}</Bar></BarChart></ResponsiveContainer></div></Card>
  </div>
  <Tip>DBSCAN finds crowded areas without being told how many to look for. {d.noise_share}% of locations are scattered “noise” that belong to no dense zone — the coloured blobs are the real hotspots, ranked by size on the right.</Tip>
 </>
}

/* ------------------------------------------------------------ APRIORI */
const FOCUS=[["all","All rules"],["strong","Strong rules (lift ≥ 1.5)"],["arrest","Rules that lead to an arrest"],["crime","Rules that explain a crime type"]];
const RuleTip=({active,payload})=>{if(!active||!payload?.length)return null;const r=payload[0].payload;return <div className="chartTip"><b>{r.from} → {r.to}</b><div>Support {r.sx.toFixed(2)}%</div><div>Confidence {r.cy.toFixed(1)}%</div><div>Lift {r.lift.toFixed(2)}</div></div>};
export function AprioriPanel({d}){
 const [focus,setFocus]=useState("strong");
 const rules=useMemo(()=>d?d.rules.map(r=>({...r,from:pretty(r.antecedents),to:pretty(r.consequents),sx:r.support*100,cy:r.confidence*100})):[],[d]);
 if(!d)return <Loading/>;
 const shown=rules.filter(r=>focus==="strong"?r.lift>=1.5:focus==="arrest"?r.consequents==="ARREST_YES":focus==="crime"?r.consequents.startsWith("CRIME_"):true);
 const seen=new Set(),top=[...shown].sort((a,b)=>b.lift-a.lift).filter(r=>{const k=[r.antecedents,r.consequents].sort().join("|");if(seen.has(k))return false;seen.add(k);return true}).slice(0,8).map(r=>({...r,label:`${r.from} → ${r.to}`}));
 const strong=shown.filter(r=>r.lift>=1.5),mid=shown.filter(r=>r.lift>=1&&r.lift<1.5),weak=shown.filter(r=>r.lift<1);
 const maxLift=Math.max(...rules.map(r=>r.lift));
 return <>
  <Stats items={[["Rules mined",rules.length,"Apriori"],["Strong rules",rules.filter(r=>r.lift>=1.5).length,"lift ≥ 1.5"],["Best lift",maxLift.toFixed(2),pretty(rules.find(r=>r.lift===maxLift)?.antecedents||"")],["Showing",shown.length,"after filter"]]}/>
  <div className="olapControls apFilter"><div className="field"><label>Focus on</label><select value={focus} onChange={e=>setFocus(e.target.value)}>{FOCUS.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div></div>
  <div className="grid2eq">
   <Card><Title title="Every rule: support vs confidence" sub="Bubble size = lift"/><div className="chart tall"><ResponsiveContainer><ScatterChart margin={{top:10,right:14,bottom:8,left:0}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="sx" name="Support" unit="%" tick={{fontSize:10}} tickFormatter={v=>Number(v).toFixed(0)} label={{value:"Support (how often the pattern occurs) %",position:"insideBottom",offset:-4,fontSize:11}} height={42}/><YAxis type="number" dataKey="cy" name="Confidence" unit="%" tick={{fontSize:10}} domain={[0,100]} width={44} label={{value:"Confidence %",angle:-90,position:"insideLeft",fontSize:11}}/><ZAxis type="number" dataKey="lift" range={[40,420]}/><Tooltip content={<RuleTip/>} cursor={{strokeDasharray:"3 3"}}/>
    <Scatter name="Lift < 1" data={weak} fill="#94a3b8" fillOpacity={.55} isAnimationActive={false}/><Scatter name="Lift 1–1.5" data={mid} fill="#3b82f6" fillOpacity={.6} isAnimationActive={false}/><Scatter name="Lift ≥ 1.5" data={strong} fill="#f97316" fillOpacity={.75} isAnimationActive={false}/><Legend verticalAlign="top" height={26}/></ScatterChart></ResponsiveContainer></div></Card>
   <Card><Title title="Strongest rules" sub="Ranked by lift"/>{top.length?<div className="ruleList">{top.map((r,i)=><div className="ruleRow" key={i}><div className="ruleText"><b>{r.from}</b><span>→</span><b>{r.to}</b></div><div className="barBg"><div className="barFill" style={{width:`${r.lift/maxLift*100}%`}}/></div><div className="ruleMeta"><em>lift {r.lift.toFixed(2)}</em><span>confidence {r.cy.toFixed(0)}%</span><span>support {r.sx.toFixed(1)}%</span></div></div>)}</div>:<div className="empty">No rules match this filter.</div>}</Card>
  </div>
  <Card className="spaced"><Title title="Most frequent items" sub="Share of all cases (frequent itemsets)"/><MiniBars rows={d.itemsets.map(x=>({label:pretty(x.itemsets),v:x.support*100}))} labelKey="label" valueKey="v" fmt={v=>v.toFixed(1)+"%"} color="#3b82f6" limit={10}/></Card>
  <Tip>Read a rule as “when we see the left side, we usually also see the right side”. <b>Confidence</b> is how often that is true, <b>support</b> how common the pattern is, and <b>lift</b> how much stronger it is than chance (above 1 = a real association, e.g. lift 4.8 means almost 5× more likely).</Tip>
 </>
}

/* ------------------------------------------------------------ PAGE */
export function PatternsPage({km,db,Spatial3D}){
 const [tab,setTab]=useState("kmeans"),[show3d,setShow3d]=useState(false),[data,setData]=useState({}),[err,setErr]=useState("");
 useEffect(()=>{let live=true;Promise.allSettled([getMiningKMeans(),getMiningDBSCAN(),getMiningApriori()]).then(r=>{if(!live)return;const v=i=>r[i].status==="fulfilled"?r[i].value.data:null;setData({kmeans:v(0),dbscan:v(1),apriori:v(2)});if(r.every(x=>x.status==="rejected"))setErr(r[0].reason?.response?.data?.detail||"Could not load mining results. Is the backend running?")});return()=>{live=false}},[]);
 const tabs=[["kmeans","K-Means","Group by location"],["dbscan","DBSCAN","Find dense zones"],["apriori","Apriori","Find co-occurring factors"]];
 return <>
  <div className="hero"><div><div className="eyebrow"><BarChart3 size={13}/> Data mining</div><h1>Patterns & hotspots</h1><p>Three mining techniques, three different questions: where does crime group, where is it densest, and which factors go together?</p></div></div>
  <div className="mineTabs">{tabs.map(([id,l,s])=><button key={id} className={tab===id?"active":""} onClick={()=>{setTab(id);setShow3d(false)}}><b>{l}</b><small>{s}</small></button>)}</div>
  {err?<Loading error={err}/>:<>
   {tab==="kmeans"&&<KMeansPanel d={data.kmeans}/>}{tab==="dbscan"&&<DBSCANPanel d={data.dbscan}/>}{tab==="apriori"&&<AprioriPanel d={data.apriori}/>}
   {tab!=="apriori"&&Spatial3D&&<div className="spaced"><button className="secondary" onClick={()=>setShow3d(s=>!s)}>{show3d?"Hide":"Show"} animated 3D view</button>{show3d&&<Spatial3D title={tab==="kmeans"?"K-Means 3D spatial view":"DBSCAN 3D density view"} subtitle="Animated cluster centres" points={(tab==="kmeans"?km?.centers:db?.centers)||[]} kind={tab}/>}</div>}</>}
 </>
}
