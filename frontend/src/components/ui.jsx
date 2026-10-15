import React from "react";
import {Info} from "lucide-react";
export function Card({children,className="",...props}){return <div className={`card ${className}`} {...props}>{children}</div>}
export function Title({title,sub}){return <div className="sectionTitle"><h3>{title}</h3>{sub&&<span>{sub}</span>}</div>}
export function Tip({children}){return <div className="tip"><Info size={14}/><span>{children}</span></div>}
export const PALETTE=["#f97316","#3b82f6","#10b981","#a855f7","#ef4444","#eab308","#06b6d4","#ec4899","#84cc16","#6366f1","#14b8a6","#f43f5e","#8b5cf6","#0ea5e9","#d97706"];
export const fmtN=n=>Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
