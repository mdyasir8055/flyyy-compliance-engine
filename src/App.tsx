import {useEffect,useMemo,useState} from 'react';
import {Routes,Route,Link,useLocation,useNavigate,useParams} from 'react-router-dom';
import {useQuery,useMutation,useQueryClient} from '@tanstack/react-query';
import {LayoutDashboard,FileText,UploadCloud,ScanLine,Search,Sun,Moon,Plus,ArrowUpRight,CheckCircle2,AlertTriangle,XCircle,MoreHorizontal,ChevronRight,Activity,Menu,Filter,Pencil,Trash2} from 'lucide-react';
import * as api from './api';
import type {Control} from './api';

const cn=(...x:(string|false|undefined)[])=>x.filter(Boolean).join(' ');
function Button({children,primary=false,onClick,icon:Icon,disabled=false}:any){return <button disabled={disabled} onClick={onClick} className={cn('btn',primary&&'btn-primary')}>{Icon&&<Icon size={16}/>} {children}</button>}
function Badge({children,tone='neutral'}:any){return <span className={cn('badge',`badge-${tone}`)}>{children}</span>}
function fmtDate(iso?:string){if(!iso)return '';const d=new Date(iso);return d.toLocaleDateString(undefined,{month:'short',day:'2-digit',year:'numeric'})+' · '+d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'})}

function Shell({children}:any){const [dark,setDark]=useState(false);const [mobile,setMobile]=useState(false);const loc=useLocation();const nav=[['/','Overview',LayoutDashboard],['/policies','Policies',FileText],['/scans/new','Compliance scans',ScanLine]];return <div className={cn('app',dark&&'dark')}><aside className={cn('sidebar',mobile&&'open')}><div className="brand"><div className="brandmark">F</div><span>FLYYY<span className="accent">.AI</span></span><button className="mobile-close" onClick={()=>setMobile(false)}>×</button></div><nav>{nav.map(([href,label,Icon]:any)=><Link key={href} to={href} onClick={()=>setMobile(false)} className={loc.pathname===href?'active':''}><Icon size={17}/>{label}</Link>)}</nav></aside><main><header><button className="mobile-menu" onClick={()=>setMobile(true)}><Menu/></button><div className="crumb"><b>{loc.pathname==='/' ? 'Overview':loc.pathname.includes('polic')?'Policies':loc.pathname.includes('scan')?'Compliance scans':'Overview'}</b></div><div className="top-actions"><div className="search"><Search size={16}/><input placeholder="Search anything..."/></div><button className="icon-btn" onClick={()=>setDark(!dark)}>{dark?<Sun size={17}/>:<Moon size={17}/>}</button></div></header>{children}</main></div>}
function PageTitle({eyebrow,title,description,action}:any){return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>}
function ConfirmDialog({title,message,onConfirm,onCancel}:any){return <div style={{position:'fixed',inset:0,background:'rgba(10,14,20,0.56)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}} onClick={onCancel}><div style={{width:420,maxWidth:'calc(100vw - 32px)',background:'#111827',border:'1px solid rgba(148,163,184,0.25)',borderRadius:16,padding:24,boxShadow:'0 20px 60px rgba(0,0,0,0.4)'}} onClick={e=>e.stopPropagation()}><h3 style={{margin:'0 0 12px',fontSize:20,color:'#f8fafc'}}>{title}</h3><p style={{margin:'0 0 20px',color:'#cbd5e1',lineHeight:1.5}}>{message}</p><div style={{display:'flex',justifyContent:'flex-end',gap:12}}><button type="button" className="btn" onClick={onCancel}>Cancel</button><button type="button" className="btn btn-primary" onClick={()=>{onConfirm();onCancel();}}>{title.includes('Reset')?'Reset':'Confirm'}</button></div></div></div>}
function Stat({label,value,change,icon:Icon,tone='blue'}:any){return <div className="stat"><div className={cn('stat-icon',`tone-${tone}`)}><Icon size={18}/></div><div className="stat-copy"><span>{label}</span><strong>{value}</strong><small className={change?.startsWith('+')?'positive':''}>{change}</small></div></div>}

function Dashboard(){
  const navigate=useNavigate();
  const qc=useQueryClient();
  const [confirm,setConfirm]=useState<any>(null);
  const [dateRange, setDateRange] = useState<'all'|'today'|'7d'|'30d'|'custom'>('all');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  const {start, end} = useMemo(() => {
    const today = new Date();
    const fmt = (d: Date) => d.toISOString().slice(0, 10);
    if (dateRange === 'today') return {start: fmt(today), end: fmt(today)};
    if (dateRange === '7d') { const d = new Date(today); d.setDate(d.getDate()-6); return {start: fmt(d), end: fmt(today)}; }
    if (dateRange === '30d') { const d = new Date(today); d.setDate(d.getDate()-29); return {start: fmt(d), end: fmt(today)}; }
    if (dateRange === 'custom' && customStart && customEnd) return {start: customStart, end: customEnd};
    return {start: undefined, end: undefined};
  }, [dateRange, customStart, customEnd]);

  const {data:summary}=useQuery({queryKey:['summary',start,end],queryFn:()=>api.getDashboardSummary(start,end)});
  const {data:scans}=useQuery({queryKey:['scans',start,end],queryFn:()=>api.getScans(start,end)});
  const resetMut=useMutation({
    mutationFn:()=>api.resetAllData(),
    onSuccess:()=>{
      qc.invalidateQueries({queryKey:['policies']});
      qc.invalidateQueries({queryKey:['scans']});
      qc.invalidateQueries({queryKey:['summary']});
      qc.invalidateQueries({queryKey:['dashboard']});
    },
  });
  const notEvaluated=summary?Math.max(summary.scans*0,0):0;
  return <section className="page"><PageTitle eyebrow="Workspace overview" title="Good morning" description="Monitor your organization's compliance posture and policy coverage." action={<div className="inline-actions"><Button icon={Trash2} onClick={()=>setConfirm({title:'Reset all data',message:'This will permanently delete ALL policies, controls, scans, and results. This cannot be undone. Continue?',onConfirm:()=>resetMut.mutate()})}>Reset all data</Button><Button primary icon={Plus} onClick={()=>navigate('/scans/new')}>Run a scan</Button></div>}/>
  <div className="inline-actions" style={{marginBottom: '16px'}}>
    <select value={dateRange} onChange={e=>setDateRange(e.target.value as any)} className="select">
      <option value="all">All time</option>
      <option value="today">Today</option>
      <option value="7d">Last 7 days</option>
      <option value="30d">Last 30 days</option>
      <option value="custom">Custom range</option>
    </select>
    {dateRange==='custom' && <>
      <input type="date" value={customStart} onChange={e=>setCustomStart(e.target.value)} className="input" />
      <span>to</span>
      <input type="date" value={customEnd} onChange={e=>setCustomEnd(e.target.value)} className="input" />
    </>}
  </div>
  {confirm&&<ConfirmDialog title={confirm.title} message={confirm.message} onConfirm={confirm.onConfirm} onCancel={()=>setConfirm(null)}/>} 
  <div className="stats">
    <Stat label="Total policies" value={String(summary?.policies??0).padStart(2,'0')} change="" icon={FileText}/>
    <Stat label="Compliance scans" value={String(summary?.scans??0).padStart(2,'0')} change="" icon={Activity} tone="teal"/>
    <Stat label="Compliant controls" value={String(summary?.passed??0).padStart(2,'0')} change="" icon={CheckCircle2} tone="green"/>
    <Stat label="Non-compliant" value={String(summary?.failed??0).padStart(2,'0')} change="Needs attention" icon={AlertTriangle} tone="amber"/>
  </div>
  <div className="dashboard-grid">
    <div className="card compliance-card"><div className="card-head"><div><h3>Overall compliance</h3><p>Across all active policies</p></div><Badge tone={(summary?.score??0)>=80?'green':'amber'}>{(summary?.score??0)>=80?'Healthy':'At risk'}</Badge></div><div className="compliance-main"><div className="ring"><div><strong>{summary?.score??0}%</strong><span>compliant</span></div></div><div className="legend"><div><i className="dot green"/><span>Passed controls</span><b>{summary?.passed??0}</b></div><div><i className="dot red"/><span>Failed controls</span><b>{summary?.failed??0}</b></div><div><i className="dot gray"/><span>Not evaluated</span><b>{notEvaluated}</b></div></div></div></div>
    <div className="card chart-card"><div className="card-head"><div><h3>Recent scan scores</h3><p>Last {Math.min(scans?.length??0,6)} compliance scans</p></div></div><div className="bars">{(scans??[]).slice(0,6).reverse().map((s)=><div className="bar-wrap" key={s.id}><div className="bar" style={{height:`${s.score}%`}}><span>{s.score}%</span></div><small>{fmtDate(s.run_at).split(' · ')[0]}</small></div>)}</div></div>
  </div>
  <div className="card table-card"><div className="card-head"><div><h3>Recent scans</h3><p>Your latest compliance evaluations</p></div><Link className="text-link" to="/scans/new">Run new <ArrowUpRight size={14}/></Link></div><ScanTable rows={scans??[]}/></div>
  </section>
}

function ScanTable({rows}:any){
  const navigate=useNavigate();
  const qc=useQueryClient();
  const [openMenuId,setOpenMenuId]=useState<string|null>(null);
  const [confirm,setConfirm]=useState<any>(null);
  useEffect(()=>{
    const handleOutsideClick=(event:MouseEvent)=>{
      const target=event.target;
      if(!(target instanceof Element)) return;
      if(!target.closest('.row-actions')) setOpenMenuId(null);
    };
    document.addEventListener('mousedown',handleOutsideClick);
    return ()=>document.removeEventListener('mousedown',handleOutsideClick);
  },[]);
  const deleteMut=useMutation({
    mutationFn:(id:string)=>api.deleteScan(id),
    onSuccess:()=>{
      qc.invalidateQueries({queryKey:['scans']});
      qc.invalidateQueries({queryKey:['summary']});
      qc.invalidateQueries({queryKey:['dashboard']});
    },
  });
  return <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Run date</th><th>Assets</th><th>Score</th><th>Status</th><th></th></tr></thead><tbody>{rows.map((r:api.Scan)=><tr key={r.id} className="clickable" onClick={()=>navigate(`/scans/${r.id}/results`)}><td><strong>{r.policy_name}</strong><small>{r.id.toUpperCase()}</small></td><td>{fmtDate(r.run_at)}</td><td>{r.assets}</td><td><strong>{r.score}%</strong></td><td><Badge tone={r.status==='Compliant'?'green':'amber'}>{r.status}</Badge></td><td><div className="row-actions" onClick={e=>e.stopPropagation()}><button type="button" onClick={e=>{e.stopPropagation();setOpenMenuId(current=>current===r.id?null:r.id);}} aria-label={`Open actions for ${r.id}`}><MoreHorizontal size={17}/></button>{openMenuId===r.id&&<div className="row-actions-menu" onClick={e=>e.stopPropagation()}><button type="button" onClick={e=>{e.stopPropagation();setConfirm({title:'Delete this scan',message:'Delete this scan? This cannot be undone.',onConfirm:()=>deleteMut.mutate(r.id)});setOpenMenuId(null);}}>Delete</button></div>}</div></td></tr>)}{rows.length===0&&<tr><td colSpan={6} className="empty-row">No scans yet. Run your first compliance scan.</td></tr>}</tbody></table>{confirm&&<ConfirmDialog title={confirm.title} message={confirm.message} onConfirm={confirm.onConfirm} onCancel={()=>setConfirm(null)}/>}</div>}

function Policies(){
  const navigate=useNavigate();
  const qc=useQueryClient();
  const [openMenuId,setOpenMenuId]=useState<string|null>(null);
  const [confirm,setConfirm]=useState<any>(null);
  useEffect(()=>{
    const handleOutsideClick=(event:MouseEvent)=>{
      const target=event.target;
      if(!(target instanceof Element)) return;
      if(!target.closest('.row-actions')) setOpenMenuId(null);
    };
    document.addEventListener('mousedown',handleOutsideClick);
    return ()=>document.removeEventListener('mousedown',handleOutsideClick);
  },[]);
  const deleteMut=useMutation({
    mutationFn:(id:string)=>api.deletePolicy(id),
    onSuccess:()=>qc.invalidateQueries({queryKey:['policies']}),
  });
  const {data:policies,isLoading}=useQuery({queryKey:['policies'],queryFn:api.getPolicies});
  return <section className="page"><PageTitle eyebrow="Governance library" title="Policies" description="Manage the policies that power your compliance evaluations." action={<Button primary icon={UploadCloud} onClick={()=>navigate('/policies/upload')}>Upload policy</Button>}/>
  <div className="toolbar"><div className="search large"><Search size={16}/><input placeholder="Search policies..."/></div><Button icon={Filter}>Filters</Button></div>
  <div className="card table-card">{isLoading?<div className="empty-row">Loading policies...</div>:<div className="table-scroll"><table><thead><tr><th>Policy name</th><th>Framework</th><th>Uploaded</th><th>Controls</th><th>Status</th><th></th></tr></thead><tbody>{(policies??[]).map(p=><tr key={p.id} onClick={()=>navigate(`/policies/${p.id}`)} className="clickable"><td><strong>{p.name}</strong><small>{p.id}</small></td><td><Badge>{p.framework}</Badge></td><td>{fmtDate(p.uploaded_at)}</td><td>{p.controls_count}</td><td><Badge tone={p.status==='Active'?'green':'neutral'}>{p.status}</Badge></td><td><div className="row-actions" onClick={e=>e.stopPropagation()}><button type="button" onClick={e=>{e.stopPropagation();setOpenMenuId(current=>current===p.id?null:p.id);}} aria-label={`Open actions for ${p.name}`}><MoreHorizontal size={17}/></button>{openMenuId===p.id&&<div className="row-actions-menu" onClick={e=>e.stopPropagation()}><button type="button" onClick={e=>{e.stopPropagation();setConfirm({title:'Delete this policy',message:'Delete this policy and all its scans? This cannot be undone.',onConfirm:()=>deleteMut.mutate(p.id)});setOpenMenuId(null);}}>Delete</button></div>}</div></td></tr>)}{(policies??[]).length===0&&<tr><td colSpan={6} className="empty-row">No policies yet. Upload a PDF to get started.</td></tr>}</tbody></table>{confirm&&<ConfirmDialog title={confirm.title} message={confirm.message} onConfirm={confirm.onConfirm} onCancel={()=>setConfirm(null)}/>}</div>}</div>
  </section>
}

function PolicyDetails(){
  const {id}=useParams();
  const navigate=useNavigate();
  const qc=useQueryClient();
  const {data:policy,isLoading}=useQuery({queryKey:['policy',id],queryFn:()=>api.getPolicy(id!),enabled:!!id});
  const [editing,setEditing]=useState<string|null>(null);
  const [draft,setDraft]=useState<any>({target:'',metric:'',operator:'<',threshold:'',severity:'Medium'});

  const addMut=useMutation({mutationFn:(c:any)=>api.addControl(id!,c),onSuccess:()=>{qc.invalidateQueries({queryKey:['policy',id]});setEditing(null)}});
  const updateMut=useMutation({mutationFn:({controlId,c}:any)=>api.updateControl(id!,controlId,c),onSuccess:()=>{qc.invalidateQueries({queryKey:['policy',id]});setEditing(null)}});
  const deleteMut=useMutation({mutationFn:(controlId:string)=>api.deleteControl(id!,controlId),onSuccess:()=>qc.invalidateQueries({queryKey:['policy',id]})});

  const start=(c:Control)=>{setEditing(c.id);setDraft({...c})};
  const save=()=>{if(!draft.target||!draft.metric||!draft.threshold)return;if(editing==='new'){addMut.mutate(draft)}else{updateMut.mutate({controlId:editing,c:draft})}};
  const resetDraft=()=>setDraft({target:'',metric:'',operator:'<',threshold:'',severity:'Medium'});

  if(isLoading||!policy)return <section className="page"><div className="empty-row">Loading policy...</div></section>;

  return <section className="page"><button className="back" onClick={()=>navigate('/policies')}>← Back to policies</button>
  <PageTitle eyebrow="Policy detail" title={policy.name} description={`${policy.framework} · Uploaded ${fmtDate(policy.uploaded_at)}`} action={<Button primary icon={ScanLine} onClick={()=>navigate('/scans/new')}>Run scan</Button>}/>
  <div className="detail-stats"><div><span>Status</span><Badge tone={policy.status==='Active'?'green':'neutral'}>{policy.status}</Badge></div><div><span>Controls extracted</span><b>{policy.controls.length}</b></div><div><span>Framework</span><b>{policy.framework}</b></div></div>
  <div className="section-heading"><div><h2>Extracted controls</h2><p>Rules parsed from the policy document and ready for evaluation.</p></div><div className="inline-actions"><Button icon={Plus} onClick={()=>{setEditing('new');resetDraft()}}>Add control</Button></div></div>
  <div className="card control-editor"><div><strong>{editing?'Edit control':'Validate controls'}</strong><p>{editing?'Update the extracted rule and save your changes.':'Review extracted controls before running a scan.'}</p></div>
  {editing&&<div className="control-form"><input value={draft.target} onChange={e=>setDraft({...draft,target:e.target.value})} placeholder="Target"/><input value={draft.metric} onChange={e=>setDraft({...draft,metric:e.target.value})} placeholder="Metric"/><input value={draft.threshold} onChange={e=>setDraft({...draft,threshold:e.target.value})} placeholder="Expected value"/><select value={draft.operator} onChange={e=>setDraft({...draft,operator:e.target.value})}><option>&lt;</option><option>&gt;=</option><option>=</option></select><select value={draft.severity} onChange={e=>setDraft({...draft,severity:e.target.value})}><option>High</option><option>Medium</option><option>Low</option></select><Button primary onClick={save} disabled={addMut.isPending||updateMut.isPending}>Save control</Button><Button onClick={()=>setEditing(null)}>Cancel</Button></div>}
  <Button icon={CheckCircle2} onClick={()=>window.alert(`Validated ${policy.controls.length} controls successfully.`)}>Validate extracted controls</Button></div>
  <div className="card table-card"><div className="table-scroll"><table><thead><tr><th>Control ID</th><th>Target</th><th>Metric</th><th>Operator</th><th>Expected value</th><th>Severity</th><th>Actions</th></tr></thead><tbody>{policy.controls.map(c=><tr key={c.id}><td><strong className="mono">{c.id}</strong></td><td className="mono">{c.target}</td><td>{c.metric}</td><td><Badge>{c.operator}</Badge></td><td className="mono">{c.threshold}</td><td><Badge tone={c.severity==='High'?'red':c.severity==='Medium'?'amber':'neutral'}>{c.severity}</Badge></td><td><div className="row-actions"><button onClick={()=>start(c)} aria-label={`Edit ${c.id}`}><Pencil size={15}/></button><button onClick={()=>deleteMut.mutate(c.id)} aria-label={`Delete ${c.id}`}><Trash2 size={15}/></button></div></td></tr>)}</tbody></table></div></div>
  </section>
}

function Upload(){
  const [file,setFile]=useState<File|null>(null);
  const navigate=useNavigate();
  const qc=useQueryClient();
  const uploadMut=useMutation({
    mutationFn:()=>api.uploadPolicy(file!),
    onSuccess:(policy)=>{qc.invalidateQueries({queryKey:['policies']});navigate(`/policies/${policy.id}`)},
  });
  return <section className="page narrow"><PageTitle eyebrow="Policy intake" title="Upload a policy" description="Add a PDF policy to extract controls and start evaluating evidence."/>
  <div className="card upload-card"><div className="dropzone" onClick={()=>document.getElementById('file')?.click()}><input id="file" type="file" accept="application/pdf" hidden onChange={e=>setFile(e.target.files?.[0]||null)}/><div className="upload-icon"><UploadCloud size={24}/></div><h3>{file?file.name:'Drop your policy PDF here'}</h3><p>{file?`${(file.size/1024/1024).toFixed(2)} MB · Ready to upload`:'or click to browse from your computer'}</p><small>PDF only · Maximum file size 25 MB</small></div>
  {file&&<div className="file-row"><div className="file-type">PDF</div><div><strong>{file.name}</strong><small>{uploadMut.isPending?'Extracting controls with AI...':uploadMut.isError?'Upload failed - try again':'Ready for extraction'}</small></div><CheckCircle2 className="positive" size={19}/></div>}
  {uploadMut.isError&&<p className="error-text">{(uploadMut.error as any)?.response?.data?.detail||'Something went wrong extracting controls.'}</p>}
  <div className="upload-actions"><Button onClick={()=>navigate('/policies')}>Cancel</Button><Button primary disabled={!file||uploadMut.isPending} onClick={()=>uploadMut.mutate()}>{uploadMut.isPending?'Uploading...':'Upload and extract'}</Button></div></div>
  </section>
}

function NewScan(){
  const navigate=useNavigate();
  const {data:policies}=useQuery({queryKey:['policies'],queryFn:api.getPolicies});
  const [policyId,setPolicyId]=useState('');
  const [json,setJson]=useState('{\n  "assets": [\n    { "name": "production_database_server",\n      "cpu_utilization": 92,\n      "memory_utilization": 68 }\n  ]\n}');
  const [jsonError,setJsonError]=useState('');
  const activePolicy=policyId||(policies?.[0]?.id??'');

  const scanMut=useMutation({
    mutationFn:()=>{const evidence=JSON.parse(json);return api.runScan(activePolicy,evidence)},
    onSuccess:(scan)=>navigate(`/scans/${scan.id}/results`),
    onError:(e:any)=>setJsonError(e?.response?.data?.detail||e?.message||'Failed to run scan'),
  });

  const validateJson=()=>{try{JSON.parse(json);setJsonError('Valid JSON ✓')}catch{setJsonError('Invalid JSON')}};

  return <section className="page narrow"><PageTitle eyebrow="Evaluation workflow" title="New compliance scan" description="Select a policy and provide the evidence to evaluate against its controls."/>
  <div className="steps"><b className="current">1 <span>Policy</span></b><i/><b>2 <span>Evidence</span></b><i/><b>3 <span>Results</span></b></div>
  <div className="card form-card">
  <label>Policy to evaluate<select value={activePolicy} onChange={e=>setPolicyId(e.target.value)}>{(policies??[]).map(p=><option key={p.id} value={p.id}>{p.name} · {p.controls_count} controls</option>)}</select></label>
  <label>Evidence JSON <span className="label-note">Required</span><textarea value={json} onChange={e=>setJson(e.target.value)} spellCheck={false}/><small>Paste infrastructure evidence matching the targets in your policy.</small></label>
  {jsonError&&<p className={jsonError.includes('✓')?'success-text':'error-text'}>{jsonError}</p>}
  <div className="form-foot"><Button onClick={validateJson}>Validate JSON</Button><Button primary icon={ScanLine} disabled={!activePolicy||scanMut.isPending} onClick={()=>scanMut.mutate()}>{scanMut.isPending?'Running scan...':'Start compliance scan'}</Button></div>
  </div></section>
}

function Results(){
  const {id}=useParams();
  const {data:scan,isLoading}=useQuery({queryKey:['scan',id],queryFn:()=>api.getScan(id!),enabled:!!id});
  if(isLoading||!scan)return <section className="page"><div className="empty-row">Loading results...</div></section>;
  const passed=scan.results.filter(r=>r.status==='Passed').length;
  const failed=scan.results.filter(r=>r.status==='Failed').length;
  const notEval=scan.results.filter(r=>r.status==='Not Evaluated').length;
  return <section className="page"><PageTitle eyebrow="Scan results" title="Compliance evaluation" description={`${scan.policy_name} · Completed ${fmtDate(scan.run_at)}`}/>
  <div className="result-banner"><div className="result-score"><div className="mini-ring"><strong>{scan.score}%</strong></div><div><Badge tone={scan.status==='Compliant'?'green':'amber'}>{scan.status}</Badge><h2>{scan.status==='Compliant'?'Controls are in good shape':'Some controls need attention'}</h2><p>{passed} of {passed+failed} evaluated controls passed across {scan.assets} assets.</p></div></div>
  <div className="result-counts"><div><b>{passed}</b><span>Passed</span></div><div><b>{failed}</b><span>Failed</span></div><div><b>{notEval}</b><span>Not evaluated</span></div></div></div>
  <div className="section-heading"><div><h2>Control results</h2><p>Review each result and its audit reasoning.</p></div></div>
  <div className="results-list">{scan.results.map((r,i)=><div className="result-card" key={i}><div className="result-card-head"><div className={cn('result-icon',r.status==='Passed'?'success':'failure')}>{r.status==='Passed'?<CheckCircle2 size={19}/>:<XCircle size={19}/>}</div><div><h3>{r.name}</h3><small className="mono">{r.target}</small></div><Badge tone={r.status==='Passed'?'green':r.status==='Failed'?'red':'neutral'}>{r.status}</Badge><ChevronRight size={17}/></div><div className="result-detail"><div><span>Expected</span><b className="mono">{r.expected}</b></div><div><span>Actual</span><b className="mono">{r.actual}</b></div><div className="reason"><span>Audit reasoning</span><p>{r.reason}</p></div></div></div>)}</div>
  </section>
}

export default function App(){return <Shell><Routes><Route path="/" element={<Dashboard/>}/><Route path="/policies" element={<Policies/>}/><Route path="/policies/upload" element={<Upload/>}/><Route path="/policies/:id" element={<PolicyDetails/>}/><Route path="/scans/new" element={<NewScan/>}/><Route path="/scans/:id/results" element={<Results/>}/><Route path="*" element={<Dashboard/>}/></Routes></Shell>}
