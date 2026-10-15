import React,{useState} from "react";
import {motion} from "framer-motion";
import {Shield,Search,Lock,User,Eye,EyeOff,ChevronRight} from "lucide-react";
import {login} from "../services/api";

const ROLES=[
 {id:"police",title:"Police",icon:Shield,blurb:"Field & station officers",can:"Prediction · Crime map · Trends"},
 {id:"crime_branch",title:"Crime Branch",icon:Search,blurb:"Investigation & analytics unit",can:"Everything + Pattern mining · OLAP · Models"},
];
const DEMO={police:["police","Police@123"],crime_branch:["crimebranch","Crime@123"]};

export default function Login({onLogin,expired}){
 const [role,setRole]=useState("police"),[username,setUsername]=useState(""),[password,setPassword]=useState(""),[show,setShow]=useState(false),[busy,setBusy]=useState(false),[err,setErr]=useState(expired?"Your session expired. Please sign in again.":"");
 const submit=async e=>{
  e?.preventDefault();setErr("");
  if(!username.trim()||!password){setErr("Enter your username and password.");return}
  setBusy(true);
  try{const r=(await login(username.trim(),password,role)).data;onLogin({token:r.token,user:r.user})}
  catch(ex){const d=ex?.response?.data?.detail;setErr(typeof d==="string"?d:(ex?.response?"Sign-in failed.":"Cannot reach the CrimeGuard API. Start the backend and try again."))}
  finally{setBusy(false)}
 };
 const fill=()=>{setUsername(DEMO[role][0]);setPassword(DEMO[role][1]);setErr("")};
 return <div className="loginPage">
  <div className="loginHero">
   <div className="brand"><div className="brandmark"><Shield size={20}/></div><div><h2>CrimeGuard</h2><small>Crime Intelligence</small></div></div>
   <div className="loginPitch"><div className="eyebrow light">Restricted access</div><h1>Predict. Locate.<br/><em>Understand crime.</em></h1><p>Machine learning, hotspot mining and a crime data warehouse — in one secure workspace for Police and Crime Branch.</p>
    <div className="radar"><span/><span/><span/><i/></div></div>
   <small className="loginFoot">Authorised personnel only · All activity is role-restricted</small>
  </div>
  <div className="loginPanel"><motion.form className="loginCard" onSubmit={submit} initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.35}}>
   <h2>Sign in</h2><p className="loginSub">Choose your unit, then enter your credentials.</p>
   <div className="roleGrid">{ROLES.map(r=>{const I=r.icon;return <button type="button" key={r.id} className={`roleCard ${role===r.id?"selected":""}`} onClick={()=>{setRole(r.id);setErr("")}}><I size={20}/><b>{r.title}</b><small>{r.blurb}</small><em>{r.can}</em></button>})}</div>
   <div className="field"><label>Username</label><div className="inputIcon"><User size={15}/><input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter username"/></div></div>
   <div className="field"><label>Password</label><div className="inputIcon"><Lock size={15}/><input autoComplete="current-password" type={show?"text":"password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter password"/><button type="button" className="eyeBtn" onClick={()=>setShow(s=>!s)} aria-label="Show password">{show?<EyeOff size={15}/>:<Eye size={15}/>}</button></div></div>
   {err&&<div className="errorBox">{err}</div>}
   <button className="primary loginBtn" disabled={busy} type="submit">{busy?"Signing in…":`Sign in as ${ROLES.find(r=>r.id===role).title}`} {!busy&&<ChevronRight size={15}/>}</button>
   <button type="button" className="demoLink" onClick={fill}>Use demo {ROLES.find(r=>r.id===role).title} account</button>
  </motion.form></div>
 </div>
}
