'use strict';
// Portal text is always assigned through textContent; mutations require an explicit button.
function createSchoolPanel(root=(typeof document!=='undefined'?document:null),options={}){
  const get=id=>root?.getElementById(id);
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node};
  const dateText=value=>value?new Date(value.slice(0,10)+'T12:00:00').toLocaleDateString('cs-CZ',{day:'numeric',month:'numeric'}):'Bez termínu';
  const pragueDay=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Prague'}).format(new Date());
  let week=0,key='',last=null;
  function urgency(value,today=pragueDay()){
    if(!value)return 'later';const day=value.slice(0,10);if(day<today)return 'overdue';if(day===today)return 'today';
    const tomorrow=new Date(today+'T12:00:00Z');tomorrow.setUTCDate(tomorrow.getUTCDate()+1);return day===tomorrow.toISOString().slice(0,10)?'tomorrow':'later';
  }
  function orderItems(items,today=pragueDay()){
    const rank={today:0,overdue:1,tomorrow:2,later:3};
    return items.slice().sort((a,b)=>rank[urgency(a.due||a.date,today)]-rank[urgency(b.due||b.date,today)]||(a.due||a.date||'9999').localeCompare(b.due||b.date||'9999'));
  }
  function detailDate(value){
    if(!value)return null;const date=new Date(value);if(!Number.isFinite(date.getTime()))return value;
    const options={timeZone:'Europe/Prague',day:'numeric',month:'numeric',year:'numeric'};
    if(value.includes('T')&&!value.includes('T00:00'))Object.assign(options,{hour:'2-digit',minute:'2-digit'});
    return date.toLocaleString('cs-CZ',options);
  }
  function close(){const dialog=get('school-detail');if(dialog?.open)dialog.close()}
  async function action(action,item){
    if(options.action)return await options.action(action,item,last);
    const response=await fetch('/school/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,item_id:item.id})});
    if(!response.ok)throw Error('Akci se nepodařilo potvrdit v Edookitu. Obnov data a zkus to znovu.');
    return await response.json();
  }
  function showMessages(){
    const dialog=get('school-detail');if(dialog.open)dialog.close();dialog.replaceChildren();dialog.dataset.itemId='messages';
    const closeButton=el('button','school-close','Zavřít ×');closeButton.onclick=close;
    dialog.append(closeButton,el('h2','','Zprávy'));
    const messages=last?.messages||[];
    if(!messages.length)dialog.append(el('p','',last?.sections?.messages==='ok'?'Žádné zprávy':'Zprávy zatím nejsou spolehlivě načtené.'));
    for(const item of messages){const row=el('button','school-message-row'+(item.unread?' unread':''));row.append(el('strong','',(item.unread?'● ':'')+(item.title||'Zpráva')),el('span','',item.creator||item.from||''),el('span','',item.description||''));row.onclick=()=>detail(item,item.title,'messages');dialog.append(row)}
    dialog.showModal();
  }
  function detail(item,title,kind){
    const dialog=get('school-detail');if(dialog.open)dialog.close();dialog.replaceChildren();
    dialog.dataset.itemId=item.id||'';
    const button=el('button','school-close','Zavřít ×');button.onclick=close;
    dialog.append(button,el('h2','',title||item.title||item.subject||'Detail'));
    const fields=[['Předmět',item.subject],['Termín',detailDate(item.due||item.date)],['Čas',[item.start,item.end].filter(Boolean).join('–')],['Učitel',item.teacher],['Místnost',item.room],['Stav',item.status||(item.cancelled?'Zrušeno':item.changed?'Změna':null)],['Zadání',item.description],['Učivo',item.topic],['Písemka',item.exam],['Poznámka',item.note]];
    for(const [label,value]of fields)if(value){const row=el('p');row.append(el('strong','',label+': '),document.createTextNode(String(value)));dialog.append(row)}
    if(last?.actions_enabled&&item.url&&(kind==='homework'||kind==='messages')){
      const command=kind==='homework'?'complete_homework':'read_message';
      const control=el('button','school-action',kind==='homework'?'Označit jako splněné':item.unread?'Přečíst a označit jako přečtené':'Zobrazit celou zprávu');
      const status=el('p','school-action-status');status.setAttribute('role','status');dialog.append(control,status);
      control.onclick=async()=>{control.disabled=true;status.textContent='Čekám na potvrzení Edookitu…';try{
        const result=await action(command,item);if(!result?.ok)throw Error('Edookit změnu nepotvrdil.');
        if(command==='complete_homework'){last={...last,homework:last.homework.filter(value=>value.id!==item.id)};key='';render(last);if(dialog.open&&dialog.dataset.itemId===item.id){control.textContent='Splněno';status.textContent='Uloženo v Edookitu'}}
        else{last={...last,messages:last.messages.map(value=>value.id===item.id?{...value,unread:false}:value)};key='';render(last);if(dialog.open&&dialog.dataset.itemId===item.id){detail({...item,description:result.detail?.text||item.description},item.title);get('school-detail').append(el('p','school-action-status','Přečteno v Edookitu'))}}
      }catch(error){if(dialog.open&&dialog.dataset.itemId===item.id){control.disabled=false;status.textContent=error.message}}};
    }
    dialog.showModal();
  }
  function renderGrid(data,target){
    const timetable=data.timetable||{},weeks=timetable.weeks||[];
    const buttons=el('div','school-weeks');weeks.slice(0,2).forEach((w,i)=>{const b=el('button',i===week?'selected':'',i?'Příští týden':'Tento týden');b.disabled=w.status!=='available';b.onclick=()=>{week=i;key='';render(last)};buttons.append(b)});
    target.append(buttons);
    const chosen=weeks[week];if(!chosen||chosen.status!=='available'){target.append(el('div','school-empty','Rozvrh pro tento týden není potvrzený.'));return}
    const start=chosen.start;const end=new Date(start+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+7);
    const days=(timetable.days||[]).filter(day=>day.date>=start&&day.date<end.toISOString().slice(0,10)&&new Date(day.date+'T12:00:00Z').getUTCDay()%6!==0);
    const bell=(timetable.bell||[]).slice().sort((a,b)=>a.period-b.period);const columns=bell.length;
    if(!columns||!days.length){target.append(el('div','school-empty','Chybí potvrzené časové sloty rozvrhu.'));return}
    const grid=el('div','school-grid');grid.style.setProperty('--school-columns',columns);grid.style.setProperty('--school-rows',days.length);
    grid.append(el('div','school-corner','Den'));
    bell.forEach((slot,i)=>{const h=el('div','school-period');h.style.gridColumn=i+2;h.style.gridRow=1;h.append(el('strong','',String(slot.period)),el('span','',`${slot.start||'—'}–${slot.end||'—'}`));grid.append(h)});
    days.forEach((day,row)=>{
      const label=el('div','school-day'+(day.date===pragueDay()?' current':''));label.style.gridRow=row+2;label.style.gridColumn=1;
      label.append(el('strong','',day.weekday_short||new Date(day.date+'T12:00:00').toLocaleDateString('cs-CZ',{weekday:'short'})),el('span','',dateText(day.date)));grid.append(label);
      bell.forEach((_,i)=>{const empty=el('div','school-slot');empty.style.gridRow=row+2;empty.style.gridColumn=i+2;grid.append(empty)});
      const lessons=(day.lessons||[]).slice().sort((a,b)=>(a.kind==='event')-(b.kind==='event'));
      const groups=new Map();
      for(const lesson of lessons){
        const begin=lesson.all_day?0:bell.findIndex(b=>b.period===lesson.period);if(begin<0)continue;
        const ending=lesson.all_day?columns-1:Math.max(begin,bell.findIndex(b=>b.period===(lesson.period_end||lesson.period)));
        const groupKey=`${begin}-${ending}`;let cell=groups.get(groupKey);
        if(!cell){cell=el('div','school-cell');cell.style.gridRow=row+2;cell.style.gridColumn=`${begin+2} / ${ending+3}`;grid.append(cell);groups.set(groupKey,cell)}
        const tile=el('button','school-lesson'+(lesson.cancelled?' cancelled':'')+(lesson.changed?' changed':'')+(lesson.kind==='event'?' school-event':''));
        let hue=0;for(const char of lesson.subject||'')hue=(hue*31+char.charCodeAt(0))%360;tile.style.setProperty('--subject-hue',hue);
        tile.append(el('strong','school-subject',lesson.subject_short||lesson.subject||'Událost'));
        const meta=[lesson.room,lesson.teacher_short||lesson.teacher].filter(Boolean).join(' · ');if(meta)tile.append(el('span','school-meta',meta));
        if(lesson.cancelled||lesson.changed)tile.append(el('span','school-change',lesson.status||(lesson.cancelled?'Zrušeno':'Změna')));
        const note=[lesson.exam?'✎ '+lesson.exam:'',lesson.note||lesson.topic].filter(Boolean).join(' · ');if(note)tile.append(el('span','school-note',note));
        tile.onclick=()=>detail(lesson,lesson.subject);tile.setAttribute('aria-label',[day.date,lesson.subject,meta,lesson.status,note].filter(Boolean).join(', '));cell.append(tile);
      }
    });target.append(grid);
  }
  function renderList(data,kind,title,target){
    const section=el('section','school-list-section');const items=orderItems(data[kind]||[]);
    section.append(el('h2','',`${title} · ${items.length}`));const list=el('div','school-list');const status=data.sections?.[kind]||'unknown';
    if(status!=='ok')section.append(el('p','school-section-warning',items.length?'Poslední známá data · synchronizace není potvrzená':'Data nejsou dostupná · nelze potvrdit prázdný seznam'));
    if(!items.length)list.append(el('div','school-empty',status==='ok'?(kind==='homework'?'Žádné úkoly':'Žádné písemky'):'Čekám na spolehlivá data…'));
    for(const item of items){const date=item.due||item.date;const urgencyClass=urgency(date);const row=el('button','school-obligation '+urgencyClass);const body=el('div');body.append(el('strong','',item.subject||'Předmět neuveden'),el('span','school-title',item.title||item.description||'Bez názvu'));if(item.description)body.append(el('span','school-description',item.description));const when=el('div','school-due');when.append(el('strong','',urgencyClass==='today'?'Dnes':urgencyClass==='tomorrow'?'Zítra':dateText(date)));if(urgencyClass==='overdue')when.append(el('span','','Po termínu'));row.append(el('span','school-kind',kind==='homework'?'▤':'✎'),body,when);row.onclick=()=>detail(item,undefined,kind);list.append(row)}
    section.append(list);target.append(section);
  }
  function render(data){
    if(!get('school-page'))return;last=data||{};
    const nextKey=JSON.stringify(data)+pragueDay()+week+Math.floor(Date.now()/60000);if(key===nextKey)return;key=nextKey;
    const messagesButton=get('school-messages');if(messagesButton){messagesButton.textContent='Zprávy · '+(data?.messages||[]).filter(message=>message.unread).length;messagesButton.onclick=showMessages}
    const status=get('school-sync'),top=get('school-timetable'),bottom=get('school-obligations');top.replaceChildren();bottom.replaceChildren();
    if(!data||data.schema_version!==1){status.textContent='Čekám na první synchronizaci';top.append(el('div','school-empty','Rozvrh se zobrazí po připojení Edookitu.'));bottom.append(el('div','school-empty','Úkoly a písemky zatím nejsou načtené.'));return}
    const age=data.last_updated?Math.max(0,(Date.now()-Date.parse(data.last_updated))/3600000):Infinity;
    status.textContent=(data.sync_status==='ok'&&age<6?'Synchronizováno':data.sync_status==='ok'?'Starší data':data.sync_status==='stale'?'Výpadek synchronizace · poslední data':'Chyba synchronizace')+(data.last_updated?' · '+new Date(data.last_updated).toLocaleString('cs-CZ',{timeZone:'Europe/Prague',day:'numeric',month:'numeric',hour:'2-digit',minute:'2-digit'}):'');status.className=data.sync_status==='ok'&&age<6?'':'school-warning';
    renderGrid(data,top);renderList(data,'homework','Úkoly',bottom);renderList(data,'exams','Písemky',bottom);
  }
  return {render,close,urgency,orderItems};
}
const SchoolPanel=createSchoolPanel();
if(typeof window!=='undefined')window.CiriSchoolRenderer={create:createSchoolPanel};
if(typeof module!=='undefined')module.exports={...SchoolPanel,createSchoolPanel};
