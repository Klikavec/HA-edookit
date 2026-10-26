import './school.js';

class EdookitSchoolCard extends HTMLElement {
  constructor(){
    super();this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML=`<link rel="stylesheet" href="${new URL('./school.css',import.meta.url)}">
      <style>:host{display:block;font-family:Roboto,sans-serif;color:#e5e5e9}*{box-sizing:border-box}ha-card{display:block;background:#131314;color:#e5e5e9;overflow:hidden}h1,h2,button,strong{color:inherit}button{font:inherit;color:inherit;background:transparent;border:1px solid transparent;border-radius:10px;cursor:pointer}button:focus-visible{outline:3px solid #a8c7fa}button:hover{filter:brightness(1.2)}#school-page{height:calc(100vh - 105px);min-height:700px;width:100%;padding:24px;display:grid;grid-template-rows:48px minmax(0,1fr) minmax(0,1fr);gap:16px}#school-detail{box-sizing:border-box}</style>
      <ha-card><section id="school-page"><header class="school-header"><h1 id="school-heading">Škola</h1><button id="school-messages">Zprávy</button><p id="school-sync" role="status"></p></header><div id="school-timetable"></div><div id="school-obligations"></div></section><dialog id="school-detail" aria-label="Detail školní položky"></dialog></ha-card>`;
    this.renderer=window.CiriSchoolRenderer.create(this.shadowRoot,{action:async(action,item,payload)=>{
      const result=await this._hass.callWS({type:'call_service',domain:'edookit',service:'school_action',
        service_data:{config_entry_id:payload.entry_id,student_id:payload.student_id||'',item_id:item.id,action},return_response:true});
      return result.response||result;
    }});
  }
  setConfig(config){if(!config.entity)throw Error('Vyber senzor školního přehledu');this.config={...config};this.shadowRoot.getElementById('school-heading').textContent=config.title||'Škola';this.refresh()}
  set hass(hass){this._hass=hass;this.refresh()}
  refresh(){const entity=this.config&&this._hass?.states[this.config.entity];this.renderer.render(entity?.attributes)}
  connectedCallback(){if(!this.timer)this.timer=setInterval(()=>this.refresh(),60000)}
  disconnectedCallback(){clearInterval(this.timer);this.timer=null;this.renderer.close()}
  getCardSize(){return 12}
}
if(!customElements.get('edookit-school-card'))customElements.define('edookit-school-card',EdookitSchoolCard);
window.customCards=window.customCards||[];
window.customCards.push({type:'edookit-school-card',name:'Edookit – školní přehled',description:'Rozvrh nahoře, úkoly a písemky dole, zprávy a explicitní školní akce.'});
