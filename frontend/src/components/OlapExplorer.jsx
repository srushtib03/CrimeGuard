import React,{useEffect,useMemo,useState} from "react";
import {BarChart,Bar,LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer,Legend} from "recharts";
import {Database,ChevronRight} from "lucide-react";
import {Card,Title,Tip,fmtN} from "./ui.jsx";
import {getOlapCatalog,askOlap} from "../services/api";

const COLORS=["#f97316","#3b82f6","#10b981"];
const GLYPH={rollup:"▲",drilldown:"▼",slice:"▭",dice:"▦",pivot:"⟲"};
const WHAT={
 rollup:"Roll-up climbs a hierarchy — daily numbers become months, months become quarters, quarters become a year. You lose detail but see the big picture.",
 drilldown:"Drill-down is the opposite: pick a group (a quarter, a district, a crime type) and break it into finer parts to see what is inside.",
 slice:"Slice fixes ONE dimension to a single value — for example only District 8, or only March — and shows everything else for that value.",
 dice:"Dice fixes SEVERAL dimensions at once (say District A and B, one crime type, across quarters) to cut out a small sub-cube.",
 pivot:"Pivot rotates the cube so one dimension runs down the rows and another across the columns, like a spreadsheet pivot table.",
};
const errText=e=>{const d=e?.response?.data?.detail;return typeof d==="string"?d:(e?.response?"Something went wrong running this question.":"Cannot reach the CrimeGuard API. Start the backend and refresh.")};

function Heat({chart,rows}){
 const cols=chart.columns,body=cols.filter(c=>c!=="Total"),max=Math.max(...rows.flatMap(r=>body.map(c=>Number(r[c]||0))),1);
 return <div className="tableWrap"><table className="table heat"><thead><tr><th>{chart.rowHeader||""}</th>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.label}><td><b>{r.label}</b></td>{cols.map(c=>{const v=Number(r[c]||0),a=c==="Total"?0:.08+.78*(v/max);return <td key={c} className={c==="Total"?"heatTotal":""} style={c==="Total"?undefined:{background:`rgba(249,115,22,${a})`,color:a>.66?"#fff":"#1f2937"}}>{fmtN(v)}</td>})}</tr>)}</tbody></table></div>
}
function Chart({chart,rows}){
 if(chart.kind==="matrix")return <Heat chart={chart} rows={rows}/>;
 const horiz=chart.horizontal,h=horiz?Math.max(280,rows.length*38+50):310;
 const common=<><CartesianGrid strokeDasharray="3 3" vertical={horiz} horizontal={!horiz}/><Tooltip formatter={(v,n)=>[fmtN(v),n]}/>{chart.series.length>1&&<Legend/>}</>;
 return <div style={{height:h}}><ResponsiveContainer>{chart.kind==="line"
  ?<LineChart data={rows} margin={{top:10,right:18,bottom:4,left:0}}>{common}<XAxis dataKey="label" tick={{fontSize:11}}/><YAxis tick={{fontSize:10}} tickFormatter={v=>fmtN(v)} width={52}/>{chart.series.map((s,i)=><Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={COLORS[i]} strokeWidth={3} dot={rows.length<=14} isAnimationActive={false}/>)}</LineChart>
  :horiz
  ?<BarChart data={rows} layout="vertical" margin={{top:6,right:26,bottom:6,left:6}}>{common}<XAxis type="number" tick={{fontSize:10}} tickFormatter={v=>fmtN(v)}/><YAxis type="category" dataKey="label" width={150} tick={{fontSize:11}}/>{chart.series.map((s,i)=><Bar key={s.key} dataKey={s.key} name={s.name} fill={COLORS[i]} radius={[0,5,5,0]} isAnimationActive={false}/>)}</BarChart>
  :<BarChart data={rows} margin={{top:10,right:18,bottom:4,left:0}}>{common}<XAxis dataKey="label" tick={{fontSize:11}}/><YAxis tick={{fontSize:10}} tickFormatter={v=>fmtN(v)} width={52}/>{chart.series.map((s,i)=><Bar key={s.key} dataKey={s.key} name={s.name} fill={COLORS[i]} radius={[5,5,0,0]} isAnimationActive={false}/>)}</BarChart>}</ResponsiveContainer></div>
}
function DataTable({res}){
 const chart=res.chart,cols=chart.kind==="matrix"?null:["label",...chart.series.map(s=>s.key),...(res.rows[0]?.arrest_rate!==undefined?["arrest_rate"]:[])];
 const names={label:"Group",crimes:"Crimes",arrests:"Arrests",arrest_rate:"Arrest rate %",no_arrest:"No arrest",a:chart.series[0]?.name,b:chart.series[1]?.name};
 if(!cols)return <Heat chart={chart} rows={res.rows}/>;
 return <div className="tableWrap"><table className="table"><thead><tr>{cols.map(c=><th key={c}>{names[c]||c}</th>)}</tr></thead><tbody>{res.rows.map((r,i)=><tr key={i}>{cols.map(c=><td key={c}>{typeof r[c]==="number"?fmtN(r[c]):r[c]}</td>)}</tr>)}</tbody></table></div>
}

export default function OlapExplorer(){
 const [cat,setCat]=useState(null),[op,setOp]=useState("rollup"),[qid,setQid]=useState(null),[params,setParams]=useState({}),[res,setRes]=useState(null),[loading,setLoading]=useState(false),[err,setErr]=useState(""),[showTable,setShowTable]=useState(false);
 useEffect(()=>{getOlapCatalog().then(r=>setCat(r.data)).catch(e=>setErr(errText(e)))},[]);
 const qs=useMemo(()=>cat?cat.questions.filter(q=>q.operation===op):[],[cat,op]);
 const pick=q=>{setQid(q.id);setParams(Object.fromEntries(q.params.map(p=>[p.name,p.default])))};
 useEffect(()=>{if(qs.length&&!qs.some(q=>q.id===qid))pick(qs[0])},[qs]);
 const q=qs.find(x=>x.id===qid),key=JSON.stringify(params);
 useEffect(()=>{if(!q)return;let live=true;setLoading(true);setErr("");askOlap(q.id,params).then(r=>live&&setRes(r.data)).catch(e=>live&&setErr(errText(e))).finally(()=>live&&setLoading(false));return()=>{live=false}},[qid,key]);
 const ops=cat?Object.entries(cat.operations):[];
 return <>
  <div className="hero"><div><div className="eyebrow"><Database size={13}/> Data warehouse / OLAP</div><h1>Ask the warehouse a question</h1><p>No SQL, no giant tables. Pick what you want to do, choose a question from the list, and read the answer.</p></div></div>
  {!cat&&!err&&<div className="empty">Loading questions…</div>}
  {err&&!cat&&<div className="errorBox">{err}</div>}
  {cat&&<>
   <Card><div className="stepHead"><span>1</span><div><b>Choose an operation</b><small>Five ways to look at the same data cube</small></div></div>
    <div className="opGrid">{ops.map(([id,o])=><button key={id} className={`opCard ${op===id?"selected":""}`} onClick={()=>{setOp(id);setShowTable(false)}}><span className="opGlyph">{GLYPH[id]}</span><b>{o.title}</b><small>{o.tagline}</small><em>{o.example}</em></button>)}</div>
    <div className="opExplain"><b>What is {cat.operations[op].title.toLowerCase()}?</b> {WHAT[op]}</div></Card>
   <Card className="spaced"><div className="stepHead"><span>2</span><div><b>Pick a question</b><small>{qs.length} questions for {cat.operations[op].title}</small></div></div>
    <div className="qControls"><div className="field qMain"><label>Question</label><select value={qid||""} onChange={e=>pick(qs.find(x=>x.id===e.target.value))}>{qs.map(x=><option key={x.id} value={x.id}>{x.question}</option>)}</select></div>
     {q?.params.map(p=><div className="field" key={p.name}><label>{p.label}</label><select value={params[p.name]??p.default} onChange={e=>setParams(s=>({...s,[p.name]:e.target.value}))}>{p.options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select></div>)}</div>
    {q?.hierarchy&&<div className="crumbs"><small>Dimensions used</small>{q.hierarchy.split(/ [→×·∈] |, /).map((h,i,a)=><React.Fragment key={i}><span className="pill">{h}</span>{i<a.length-1&&<ChevronRight size={12}/>}</React.Fragment>)}</div>}</Card>
   <Card className="spaced olapResult"><div className="stepHead"><span>3</span><div><b>Answer</b><small>{loading?"Running query…":"Updated automatically when you change a dropdown"}</small></div></div>
    {err&&<div className="errorBox">{err}</div>}
    {res&&<><div className="answerBox"><b>{res.question}</b><p>{res.summary}</p></div><Chart chart={res.chart} rows={res.rows}/>
     {res.chart.kind!=="matrix"&&<><button className="linkBtn tableToggle" onClick={()=>setShowTable(s=>!s)}>{showTable?"Hide":"Show"} the numbers behind this chart</button>{showTable&&<DataTable res={res}/>}</>}</>}
    {!res&&!err&&<div className="empty">{loading?"Running query…":"Select a question to see the answer."}</div>}</Card>
   <Tip>Every answer comes straight from the CrimeGuard data warehouse (fact table + crime and location dimensions) — the same data used everywhere else in the project.</Tip></>}
 </>
}
