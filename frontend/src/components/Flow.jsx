import React from "react";
import {Check,ChevronRight,ChevronLeft} from "lucide-react";

export const CRIME_ONLY=["explain","patterns","olap","models"];
export const FLOWS={
 police:[["dashboard","Overview","See the big picture of crime in the city"],["prediction","Predict","Estimate the arrest likelihood for a case"],["map","Hotspots","Find where crime clusters on the map"],["trends","Trends","Spot the busiest hours, months and categories"]],
 crime_branch:[["dashboard","Overview","See the big picture of crime in the city"],["prediction","Predict","Estimate the arrest likelihood for a case"],["explain","Explain","Understand why the model decided that"],["map","Hotspots","Find where crime clusters on the map"],["trends","Trends","Spot the busiest hours, months and categories"],["patterns","Mine patterns","Inspect K-Means, DBSCAN and Apriori results"],["olap","Ask the warehouse","Answer questions with Roll-up, Drill-down, Slice, Dice, Pivot"],["models","Compare models","Check which model performs best"]],
};

export function FlowBar({flow,page,setPage,visited}){
 const idx=flow.findIndex(s=>s[0]===page);
 return <div className="flowBar" role="navigation" aria-label="Workflow">{flow.map(([id,label],i)=>{const done=visited.has(id)&&id!==page,cur=id===page;return <React.Fragment key={id}><button className={`flowStep ${cur?"current":""} ${done?"done":""}`} onClick={()=>setPage(id)}><span className="flowNum">{done?<Check size={12}/>:i+1}</span><span>{label}</span></button>{i<flow.length-1&&<span className={`flowLine ${i<idx?"filled":""}`}/>}</React.Fragment>})}</div>
}

export function FlowFooter({flow,page,setPage}){
 const i=flow.findIndex(s=>s[0]===page); if(i<0)return null;
 const prev=flow[i-1],next=flow[i+1];
 return <div className="flowFooter">{prev?<button className="secondary" onClick={()=>setPage(prev[0])}><ChevronLeft size={15}/> Back: {prev[1]}</button>:<span/>}
  {next?<button className="primary nextBtn" onClick={()=>setPage(next[0])}><span><small>Next step · {next[2]}</small>{next[1]}</span><ChevronRight size={16}/></button>:<span className="flowDone"><Check size={15}/> You have completed the workflow</span>}</div>
}
