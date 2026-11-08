/* Tiny Family: own Home Assistant panel, independent of Lovelace. */
const TF_VIEWS = [
  ["live", "Kort", "mdi:map-marker-multiple-outline"],
  ["places", "Steder", "mdi:map-marker-radius-outline"],
  ["activity", "Aktivitet", "mdi:walk"],
  ["contact", "Beskeder", "mdi:message-text-outline"]
];
const TF_MORE_VIEWS = [
  ["today", "Min status", "mdi:home-outline"],
  ["routes", "GPS-ruter", "mdi:map-outline"],
  ["history", "Hændelser", "mdi:history"],
  ["help", "Hjælp", "mdi:help-circle-outline"]
];
class TinyFamilyPanel extends HTMLElement {
  constructor() { super(); this.active = "live"; this.booted = false; this.settings = null; }
  set hass(value) {
    this.hassInstance = value;
    if (this.isConnected && !this.booted) this.initialize();
    if (this.card) this.card.hass = value;
    if (this.active === "today" && this._todayPerson) this.updateToday();
  }
  set narrow(value) { this.isNarrow = value; }
  set panel(value) { this.panelInfo = value; }
  connectedCallback() { if (this.hassInstance && !this.booted) this.initialize(); }
  disconnectedCallback() {
    if(this._familyTimer){clearInterval(this._familyTimer);this._familyTimer=null;}
    if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
  }
  async initialize() {
    if (this.loading || this.booted) return;
    this.loading = true;
    this.innerHTML = `
      <style>
      tiny-family-panel{display:block;background:var(--primary-background-color);min-height:100%;color:var(--primary-text-color)}
      .tf-wrap{max-width:1280px;padding:clamp(12px,2.6vw,24px);margin:auto;font-family:inherit;box-sizing:border-box;min-width:0}
      .tf-wrap *{box-sizing:border-box;min-width:0}
      .tf-wrap button,.tf-wrap select,.tf-wrap input,.tf-wrap textarea{font:inherit}
      .tf-wrap button{touch-action:manipulation}
      .tf-wrap button:focus-visible,.tf-wrap a:focus-visible,.tf-wrap input:focus-visible,.tf-wrap select:focus-visible,.tf-wrap textarea:focus-visible{outline:3px solid var(--primary-color);outline-offset:2px}
      .tf-wrap button:disabled{opacity:.55;cursor:wait}
      .tf-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,185px),1fr));gap:10px}
      .tf-stat{display:grid;gap:5px;border:1px solid var(--divider-color);padding:12px;border-radius:12px;background:var(--card-background-color);overflow-wrap:anywhere}
      .tf-stat strong{font-size:.8rem;color:var(--secondary-text-color)}
      .tf-stat [data-today-metric]{font-weight:600;font-variant-numeric:tabular-nums}
      .tf-card-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px}
      .tf-chip{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--divider-color);padding:4px 9px;border-radius:999px;font-size:.78rem;color:var(--secondary-text-color);max-width:100%;overflow-wrap:anywhere}
      .tf-card-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
      .tf-card-actions>*{flex:0 1 auto}
      .tf-map{height:clamp(295px,48vh,520px);min-height:295px;max-width:100%;border:1px solid var(--divider-color);border-radius:14px;overflow:hidden}
      .tf-empty{padding:18px;border:1px dashed var(--divider-color);border-radius:12px;color:var(--secondary-text-color)}
      .tf-wrap a{color:var(--primary-color)}
      .tf-person p{margin:4px 0;overflow-wrap:anywhere}
      .tf-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
      .tf-head h1{flex:1;min-width:0}
      .tf-header-action{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-height:44px;min-width:44px;padding:8px;border:1px solid var(--divider-color);border-radius:12px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}
      .tf-more{position:relative}
      .tf-more summary{list-style:none;cursor:pointer}
      .tf-more summary::-webkit-details-marker{display:none}
      .tf-more-menu{position:absolute;z-index:120;right:0;top:calc(100% + 6px);width:210px;max-width:calc(100vw - 30px);display:grid;gap:4px;padding:8px;border-radius:14px;border:1px solid var(--divider-color);background:var(--card-background-color);box-shadow:0 12px 30px rgba(0,0,0,.2)}
      .tf-more-menu button{display:flex;align-items:center;gap:8px;text-align:left;min-height:43px;padding:8px 10px;border:0;border-radius:9px;color:var(--primary-text-color);background:transparent}
      .tf-map-tools{border:1px solid var(--divider-color);border-radius:12px;padding:8px 12px;margin:0 0 12px;background:var(--card-background-color)}
      .tf-map-tools summary{cursor:pointer;font-weight:600;padding:6px 0}
      .tf-map-tools>*:not(summary){margin-top:10px}
      .tf-shared-place-form{display:grid;gap:10px}
      .tf-shared-place-form label{display:grid;gap:5px}
      .tf-shared-place-form input{width:100%;padding:10px;border:1px solid var(--divider-color);border-radius:9px;background:var(--primary-background-color);color:var(--primary-text-color)}
      .tf-shared-place-actions{display:flex;flex-wrap:wrap;gap:8px}
      .tf-shared-place-actions>*{flex:1 1 150px}
      .tf-place-group{margin:15px 0}
      .tf-place-group>summary{padding:10px 0;cursor:pointer;font-weight:600}
      .tf-head h1{margin:0;font-size:24px}
      .tf-tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;max-width:100%}
      .tf-tabs button{display:flex;align-items:center;justify-content:center;gap:7px;padding:12px 16px;min-height:44px;border-radius:14px;border:1px solid var(--divider-color);color:var(--primary-text-color);background:var(--card-background-color);cursor:pointer}
      .tf-tabs button ha-icon{--mdc-icon-size:20px}
      .tf-tabs button[data-view=editor]{border-color:var(--primary-color);font-weight:700}
      .tf-admin-panel{border:2px solid var(--primary-color);border-radius:16px;padding:clamp(12px,2vw,20px);background:var(--card-background-color)}
      .tf-admin-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .tf-admin-head ha-icon{color:var(--primary-color)}
      .tf-advanced{padding:10px;border:1px solid var(--divider-color);border-radius:12px}
      .tf-advanced summary{cursor:pointer;font-weight:600;padding:5px}
      .tf-advanced .tf-fields{margin-top:10px}
      .tf-tabs button[aria-current=page]{border-color:var(--primary-color);color:var(--primary-color)}
      .tf-person{display:grid;gap:8px;padding:12px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:12px;margin-bottom:10px}
      .tf-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,170px),1fr));gap:10px;max-width:100%}
      .tf-fields label{display:grid;gap:4px;font-size:13px}
      .tf-fields select,.tf-fields input{padding:7px;max-width:100%;background:var(--primary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:8px}
      .tf-save{background:var(--primary-color);color:var(--text-primary-color,#fff);border:0;border-radius:10px;padding:12px 18px;min-height:44px;cursor:pointer;overflow-wrap:anywhere}
      .tf-message{margin:14px 0;color:var(--secondary-text-color)}
      @media(max-width:600px){
        .tf-wrap{padding:10px 10px calc(100px + env(safe-area-inset-bottom))}.tf-head h1{font-size:21px}
        .tf-head{margin-bottom:8px}
        .tf-tabs{position:fixed;left:0;right:0;bottom:0;z-index:100;background:var(--card-background-color);border-top:1px solid var(--divider-color);padding:7px 8px calc(7px + env(safe-area-inset-bottom));box-shadow:0 -4px 20px rgba(0,0,0,.08)}
        .tf-family-view>.tf-map{height:calc(100dvh - 210px);min-height:380px;max-height:750px;border-radius:18px}
        .tf-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;overflow:visible}
        .tf-tabs button{display:flex;flex-direction:column;gap:3px;font-size:11px;line-height:1.2;padding:7px 2px;min-height:58px;white-space:normal;text-align:center;border-radius:10px}
        .tf-tabs button ha-icon{--mdc-icon-size:21px}
        .tf-fields{grid-template-columns:1fr}
        .tf-metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
        .tf-stat{padding:10px}
        .tf-person{padding:11px}.tf-map{height:min(57vh,440px);min-height:330px}
        .tf-family-view>.tf-map{height:calc(100dvh - 210px);min-height:380px;max-height:750px}
        .tf-card-actions>*{flex:1 1 100%}
        .tf-wrap .tf-save{width:100%}
        .tf-admin-panel{padding:12px}
      }
      @media(max-width:360px){
        .tf-fields,.tf-metrics{grid-template-columns:1fr}
      }
      @media(prefers-reduced-motion:reduce){.tf-tabs{scroll-behavior:auto}}
      </style>
      <section class="tf-wrap"><header class="tf-head"><ha-icon icon="mdi:account-group"></ha-icon><h1>Tiny Family</h1><div class="tf-admin-access"></div><details class="tf-more"><summary class="tf-header-action" aria-label="Flere funktioner"><ha-icon icon="mdi:dots-horizontal"></ha-icon></summary><div class="tf-more-menu"></div></details></header>
      <nav class="tf-tabs" aria-label="Tiny Family"></nav>
      <p id="tf-message" class="tf-message" aria-live="polite"></p>
      <main id="tf-main"></main></section>`;
    const tabs = this.querySelector(".tf-tabs");
    try {
      // Only an authenticated administrator gets the Administration tab.
      await this.refreshSettings();
      for (const [key, title, icon] of TF_VIEWS) {
        const button = document.createElement("button");
        const pictogram=document.createElement("ha-icon");
        pictogram.setAttribute("icon",icon);
        pictogram.setAttribute("aria-hidden","true");
        const caption=document.createElement("span");caption.textContent=title;
        button.append(pictogram,caption);
        button.dataset.view = key;
        button.type="button";
        button.addEventListener("click", () => this.show(key));
        tabs.appendChild(button);
      }
      const moreMenu=this.querySelector(".tf-more-menu");
      for(const [key,title,icon] of TF_MORE_VIEWS){
        const button=document.createElement("button");
        button.type="button";
        const pictogram=document.createElement("ha-icon");
        pictogram.setAttribute("icon",icon);
        button.append(pictogram,document.createTextNode(title));
        button.addEventListener("click",()=>{
          this.querySelector(".tf-more").open=false;
          this.show(key);
        });
        moreMenu.appendChild(button);
      }
      if(this.settings.editable){
        const adminButton=document.createElement("button");
        adminButton.type="button";
        adminButton.className="tf-header-action";
        adminButton.title="Administration";
        adminButton.setAttribute("aria-label","Åbn administration");
        const shield=document.createElement("ha-icon");
        shield.setAttribute("icon","mdi:shield-crown-outline");
        adminButton.append(shield);
        adminButton.addEventListener("click",()=>this.show("editor"));
        this.querySelector(".tf-admin-access").appendChild(adminButton);
      }
      try {
        const profile=await this.hassInstance.callApi("GET","tiny_family/status");
        this._viewerPerson=profile.viewer_person;
      } catch(error) {this._viewerPerson=null;}
      this.booted = true;
      this.show(this.active);
    } catch (error) { this.message("Fejl ved indlæsning: " + String(error), true); }
    finally { this.loading = false; }
  }
  message(value, error=false) {
    const target = this.querySelector("#tf-message");
    if (target) {
      target.textContent = value;
      target.style.color = error ? "var(--error-color)" : "";
      target.setAttribute("role", error ? "alert" : "status");
    }
  }
  errorText(error) {
    const code = error?.body?.error_code || error?.error_code;
    const explanations={
      no_recipient:"Ingen telefonmodtager er tilknyttet. Kontakt en administrator.",
      invalid_recipient:"Modtageren er ikke længere tilknyttet. Opdater beskedlisten.",
      gps_unavailable:"Der er ingen frisk GPS-position. Beskeden kan sendes uden position.",
      notify_failed:"Ingen notifikationer blev accepteret. Kontrollér Companion-forbindelsen, og prøv igen.",
      rate_limited:"Vent et øjeblik før du forsøger igen.",
      not_linked:"Din HA-konto er ikke tilknyttet et familiemedlem. Kontakt administrator.",
      invalid_action:"Denne handling kan ikke udføres med de aktuelle valg."
    };
    return explanations[code] || error?.body?.message || error?.message || String(error);
  }
  async refreshSettings() {
    this.settings = await this.hassInstance.callApi("GET", "tiny_family/settings");
  }
  show(key) {
    if (!this.booted) return;
    if (key === "editor" && !this.settings?.editable) key = "live";
    this.active = key; this.card = null; this._todayPerson = null; this.message("");
    if(this._familyTimer){clearInterval(this._familyTimer);this._familyTimer=null;}
    if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
    this.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-current", b.dataset.view === key ? "page" : "false"));
    const root = this.querySelector("#tf-main");
    root.classList.toggle("tf-admin-panel",key==="editor");
    root.classList.toggle("tf-family-view",key==="live");
    root.replaceChildren();
    if (key === "editor") { this.editor(root); return; }
    if (key === "contact") { this.contact(root); return; }
    if (key === "history") { this.history(root); return; }
    if (key === "activity") { this.activity(root); return; }
    if (key === "today") { this.today(root); return; }
    if (key === "live") { this.family(root); return; }
    if (key === "places") { this.places(root); return; }
    if (key === "routes") { this.routes(root); return; }
    if (key === "help") { this.help(root); return; }
    this.message("Ukendt Tiny Family-visning.", true);
  }

  async leaflet() {
    // HA renders custom panels inside nested shadow roots. A stylesheet in
    // document.head does not style Leaflet descendants within that root.
    // Place Leaflet's layout CSS in the *nearest* shadow root of this panel.
    if(!this._leafletStylesLoading){
      this._leafletStylesLoading=new Promise((resolve,reject)=>{
        const root=this.getRootNode();
        const host=(typeof ShadowRoot!=="undefined" &&
                    root instanceof ShadowRoot)?root:document.head;
        let link=host.querySelector('link[data-tiny-family-leaflet]');
        if(link && link.sheet){resolve();return;}
        if(!link){
          link=document.createElement("link");
          link.rel="stylesheet";
          link.dataset.tinyFamilyLeaflet="1";
          link.href="/person_timeline_static/leaflet/leaflet.css";
          link.addEventListener("load",resolve,{once:true});
          link.addEventListener("error",()=>reject(new Error(
            "Leaflet CSS kunne ikke indlæses.")),{once:true});
          host.appendChild(link);
        }else{
          link.addEventListener("load",resolve,{once:true});
          link.addEventListener("error",()=>reject(new Error(
            "Leaflet CSS kunne ikke indlæses.")),{once:true});
        }
      }).catch(error=>{this._leafletStylesLoading=null;throw error;});
    }
    await this._leafletStylesLoading;
    if(window.L)return window.L;
    if(!this._leafletLoading){
      this._leafletLoading=new Promise((resolve,reject)=>{
        const script=document.createElement("script");
        script.src="/person_timeline_static/leaflet/leaflet.js";
        script.onload=()=>resolve(window.L);
        script.onerror=()=>reject(new Error(
          "Leaflet JavaScript kunne ikke indlæses."));
        document.head.appendChild(script);
      }).catch(error=>{this._leafletLoading=null;throw error;});
    }
    return await this._leafletLoading;
  }

  createLeafletMap(element) {
    const map=window.L.map(element,{zoomControl:true});
    this._familyMap=map;
    let frame=0;
    const update=()=>{
      if(frame || this._familyMap!==map || !element.isConnected)return;
      frame=requestAnimationFrame(()=>{
        frame=0;
        if(this._familyMap===map && element.isConnected)
          map.invalidateSize({pan:false,animate:false});
      });
    };
    // Leaflet measures its viewport when the map is created. HA sidebars,
    // responsive breakpoints, mobile rotations and Playwright viewport
    // changes can resize that element without a window resize event.
    const observer=typeof ResizeObserver!=="undefined"
      ?new ResizeObserver(update):null;
    observer?.observe(element);
    window.addEventListener("resize",update);
    map.on("unload",()=>{
      observer?.disconnect();
      window.removeEventListener("resize",update);
      if(frame)cancelAnimationFrame(frame);
    });
    update();
    return map;
  }

  // The built-in HA map_tiles proxy was introduced in HA 2026.9. It avoids
  // 403/Referer problems on OSM's volunteer tile server and caches tiles in HA.
  // Keep Leaflet for editable circles/polygons and route layers.
  async mapTilesAccessToken(force=false) {
    const connection=this.hassInstance?.connection;
    const enabled=this.hassInstance?.config?.components?.includes("map_tiles");
    if(!enabled || !connection?.sendMessagePromise)return null;
    if(!force && this._mapTilesAuth &&
       Date.now()-this._mapTilesAuth.at<20*60*1000)return this._mapTilesAuth.token;
    if(!this._mapTilesPending){
      this._mapTilesPending=connection.sendMessagePromise({
        type:"map_tiles/access_token"
      }).then(result=>{
        if(typeof result?.token!=="string" || !result.token)
          throw new Error("Home Assistant gav ingen kortadgang.");
        this._mapTilesAuth={token:result.token,at:Date.now()};
        return result.token;
      }).finally(()=>{this._mapTilesPending=null;});
    }
    return this._mapTilesPending;
  }

  async addBaseMap(map, element) {
    const feedback=document.createElement("div");
    feedback.className="tf-map-feedback tf-message";
    feedback.setAttribute("role","status");
    const old=element.nextElementSibling;
    if(old?.classList?.contains("tf-map-feedback"))old.remove();
    element.insertAdjacentElement("afterend",feedback);
    const hasProxy=this.hassInstance?.config?.components?.includes("map_tiles");
    const L=window.L;
    const directUrl="https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    let layer=null;
    let failures=0;
    let lastRecovery=0;
    let mode="";
    const notice=(content,allowDirect=false)=>{
      feedback.dataset.error="1";
      feedback.replaceChildren();
      const span=document.createElement("span");
      span.textContent=content;
      feedback.appendChild(span);
      const retry=document.createElement("button");
      retry.type="button";retry.className="tf-save";
      retry.textContent="Prøv kort igen";
      retry.addEventListener("click",async()=>{
        retry.disabled=true;
        try{
          if(mode==="ha"){
            const newToken=await this.mapTilesAccessToken(true);
            setLayer("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                     encodeURIComponent(newToken),"ha");
          }else setLayer(directUrl,"osm");
        }catch(error){notice("Home Assistant-kortet kan ikke genindlæses: "+
                             error.message,allowDirect);}
        finally{retry.disabled=false;}
      });
      feedback.appendChild(retry);
      if(allowDirect){
        const fallback=document.createElement("button");
        fallback.type="button";fallback.className="tf-save";
        fallback.textContent="Brug OpenStreetMap direkte";
        fallback.addEventListener("click",()=>{
          if(!window.confirm("Direkte OpenStreetMap kan se kortområdet og "+
            "din Home Assistant-adresses oprindelse (Referer). Fortsæt?"))return;
          this._directTilesAllowed=true;
          setLayer(directUrl,"osm");
        });
        feedback.appendChild(fallback);
      }
    };
    const setLayer=(url,source)=>{
      if(layer)map.removeLayer(layer);
      mode=source;failures=0;
      feedback.replaceChildren();
      feedback.dataset.error="0";
      const status=document.createElement("span");
      status.textContent=source==="ha"
        ?"Kortgrundlag: Home Assistants indbyggede kortfliser."
        :"Kortgrundlag: OpenStreetMap direkte (alternativ).";
      feedback.appendChild(status);
      layer=L.tileLayer(url,{
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom:19,maxNativeZoom:19,
        // Direct browser requests must send Referer under the OSM tile policy.
        referrerPolicy:"origin",
        crossOrigin:false,
      });
      let retryCount=0;
      let retryTimer=null;
      map.once("unload",()=>{if(retryTimer)clearTimeout(retryTimer);});
      layer.on("tileload",()=>{
        if(map!==this._familyMap || feedback.dataset.error==="1")return;
        const images=Array.from(map.getContainer().querySelectorAll("img.leaflet-tile"));
        if(images.length && images.every(image=>
           image.complete && image.naturalWidth>0 &&
           image.classList.contains("leaflet-tile-loaded"))){
          const status=feedback.querySelector("span");
          if(status)status.textContent=source==="ha"
            ?"Kortgrundlag indlæst via Home Assistant."
            :"Kortgrundlag indlæst fra OpenStreetMap.";
        }
      });
      layer.on("tileerror",()=>{
        failures++;
        if(retryCount<2 && !retryTimer){
          retryTimer=setTimeout(()=>{
            retryTimer=null;
            if(map!==this._familyMap || mode!==source)return;
            retryCount++;
            layer.redraw();
          },retryCount?6500:2500);
        }
        if(failures>=3 && Date.now()-lastRecovery>15000){
          lastRecovery=Date.now();
          notice(source==="ha"
            ?"Home Assistant kunne ikke hente kortfliser. Personer, "+
             "zoner og tegning virker stadig. Du kan prøve igen eller vælge "+
             "direkte kortfliser."
            :"OpenStreetMap afviste kortfliserne. Kontrollér forbindelsen "+
             "og browserens Referer-indstillinger.", source==="ha");
        }
      });
      layer.addTo(map);
      map._tinyFamilyBaseLayer=layer;
      map._tinyFamilyMapSource=source;
      // The HA token is good for at least 30 minutes, but the map may sit
      // open over a rotation. Renew while visible, never log or store token.
      if(source==="ha"){
        const onMove=async()=>{
          if(map!==this._familyMap || !element.isConnected)return;
          if(Date.now()-(this._mapTilesAuth?.at||0)<20*60*1000)return;
          try{
            const token=await this.mapTilesAccessToken(true);
            if(map===this._familyMap && mode==="ha"){
              layer.setUrl("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                encodeURIComponent(token));
            }
          }catch(error){notice("Kunne ikke forny Home Assistant-kortadgang. "+
                               "Prøv igen.",true);}
        };
        map.on("moveend",onMove);
      }
    };
    if(hasProxy && !this._directTilesAllowed){
      try{
        const token=await this.mapTilesAccessToken();
        if(map!==this._familyMap || !element.isConnected)return;
        setLayer("/api/map_tiles/raster/{z}/{x}/{y}.png?token="+
                 encodeURIComponent(token),"ha");
      }catch(error){
        notice("Home Assistants kortfliser kunne ikke aktiveres. "+
          "Korttegning er stadig tilgængelig: "+error.message,true);
      }
    }else{
      if(map===this._familyMap && element.isConnected)setLayer(directUrl,"osm");
    }
  }

  async places(root) {
    const title=document.createElement("h2");
    title.textContent="Familiens steder";root.appendChild(title);
    const intro=document.createElement("p");intro.className="tf-message";
    intro.textContent="Fælles steder er synlige for alle familiemedlemmer. Du kan oprette og redigere dine egne. Administrator kan ændre alle steder.";
    root.appendChild(intro);

    const create=document.createElement("section");create.className="tf-person";
    const head=document.createElement("strong");head.textContent="Tilføj et fælles sted";
    create.appendChild(head);
    const form=document.createElement("form");form.className="tf-shared-place-form";
    const nameLabel=document.createElement("label");
    nameLabel.textContent="Stedets navn";
    const name=document.createElement("input");name.type="text";name.maxLength=80;
    name.required=true;name.placeholder="Fx Skole, Arbejde eller Bedstemor";
    nameLabel.appendChild(name);form.appendChild(nameLabel);
    const hint=document.createElement("p");hint.className="tf-message";
    hint.textContent="Vælg et punkt på kortet, eller brug din seneste friske GPS-position.";
    form.appendChild(hint);
    const pointMap=document.createElement("div");pointMap.className="tf-map";
    pointMap.style.height="260px";pointMap.style.minHeight="260px";
    form.appendChild(pointMap);
    const coords=document.createElement("details");
    const coordsTitle=document.createElement("summary");
    coordsTitle.textContent="Koordinater (kan også indtastes)";
    coords.appendChild(coordsTitle);
    const coordRow=document.createElement("div");coordRow.className="tf-fields";
    const latLabel=document.createElement("label");latLabel.textContent="Breddegrad";
    const lat=document.createElement("input");lat.type="number";lat.step="any";lat.min="-90";lat.max="90";
    latLabel.appendChild(lat);
    const lonLabel=document.createElement("label");lonLabel.textContent="Længdegrad";
    const lon=document.createElement("input");lon.type="number";lon.step="any";lon.min="-180";lon.max="180";
    lonLabel.appendChild(lon);coordRow.append(latLabel,lonLabel);coords.appendChild(coordRow);
    form.appendChild(coords);
    const actions=document.createElement("div");actions.className="tf-shared-place-actions";
    const position=document.createElement("button");position.type="button";
    position.className="tf-save";position.textContent="Brug min position";
    const submit=document.createElement("button");submit.type="submit";
    submit.className="tf-save";submit.textContent="Gem som fælles sted";
    actions.append(position,submit);form.appendChild(actions);
    create.appendChild(form);root.appendChild(create);
    const sharedTitle=document.createElement("h3");sharedTitle.textContent="Fælles steder";
    root.appendChild(sharedTitle);
    const sharedList=document.createElement("div");root.appendChild(sharedList);
    const ownDetails=document.createElement("details");ownDetails.className="tf-place-group";
    const ownTitle=document.createElement("summary");ownTitle.textContent="Mine registrerede ophold";
    ownDetails.appendChild(ownTitle);
    const ownList=document.createElement("div");ownDetails.appendChild(ownList);
    root.appendChild(ownDetails);
    const adminDetails=document.createElement("details");adminDetails.className="tf-place-group";
    const adminTitle=document.createElement("summary");
    adminTitle.textContent="Administrator: destinationer og opholdsforslag";
    adminDetails.appendChild(adminTitle);
    const adminList=document.createElement("div");adminDetails.appendChild(adminList);

    let map=null,chosen=null,marker=null;
    const choose=(latitude,longitude)=>{
      if(!Number.isFinite(latitude)||!Number.isFinite(longitude))return;
      chosen={latitude:Number(latitude.toFixed(6)),longitude:Number(longitude.toFixed(6))};
      lat.value=String(chosen.latitude);lon.value=String(chosen.longitude);
      if(map){
        if(marker)marker.remove();
        marker=window.L.circleMarker([latitude,longitude],{
          radius:9,weight:2,color:"#fff",fillColor:"#9c56c4",fillOpacity:1
        }).addTo(map);
        map.setView([latitude,longitude],Math.max(14,map.getZoom()));
      }
    };
    try{
      await this.leaflet();
      if(this.active!=="places")return;
      map=this.createLeafletMap(pointMap);
      await this.addBaseMap(map,pointMap);
      map.setView([
        this.hassInstance.config.latitude||0,
        this.hassInstance.config.longitude||0
      ],11);
      map.on("click",event=>choose(event.latlng.lat,event.latlng.lng));
      setTimeout(()=>{if(this._familyMap===map)map.invalidateSize();},150);
    }catch(error){
      hint.textContent="Kortet kunne ikke indlæses. Du kan stadig angive koordinater manuelt.";
    }

    const fill=(place,defaultName="")=>{
      name.value=defaultName || (place.name==="Ukendt sted"?"":place.name)||"";
      choose(Number(place.latitude),Number(place.longitude));
      create.scrollIntoView({behavior:"smooth",block:"start"});
      name.focus();
    };
    const call=async(method,payload,success)=>{
      try{
        await this.hassInstance.callApi(method,"tiny_family/places",payload);
        this.message(success);
        await load();
        return true;
      }catch(error){this.message("Stedet kunne ikke gemmes: "+this.errorText(error),true);return false;}
    };
    const openMaps=place=>{
      const link=document.createElement("a");
      link.textContent="Vis i kortapp";
      link.href="https://www.google.com/maps/search/?api=1&query="+
        encodeURIComponent(place.latitude+","+place.longitude);
      link.target="_blank";link.rel="noopener noreferrer";
      return link;
    };
    const labelInput=(title,value)=>{
      const wrapper=document.createElement("label");wrapper.textContent=title;
      const input=document.createElement("input");
      input.type="text";input.value=String(value ?? "");
      input.style.cssText="width:100%;padding:9px;color:var(--primary-text-color);background:var(--primary-background-color);border:1px solid var(--divider-color);border-radius:9px";
      wrapper.appendChild(input);return {wrapper,input};
    };
    const load=async()=>{
      const data=await this.hassInstance.callApi("GET","tiny_family/places");
      if(this.active!=="places")return;
      sharedList.replaceChildren();ownList.replaceChildren();adminList.replaceChildren();
      for(const place of data.shared_places||[]){
        const card=document.createElement("section");card.className="tf-person";
        const heading=document.createElement("strong");heading.textContent=place.name;
        const meta=document.createElement("p");
        meta.className="tf-message";
        meta.textContent="Oprettet af "+(place.created_by_name||"Familiemedlem");
        card.append(heading,meta,openMaps(place));
        if(place.can_edit){
          const edit=document.createElement("details");
          const editTitle=document.createElement("summary");editTitle.textContent="Rediger sted";
          edit.appendChild(editTitle);
          const newName=labelInput("Navn",place.name);
          const newLat=labelInput("Breddegrad",place.latitude);
          const newLon=labelInput("Længdegrad",place.longitude);
          edit.append(newName.wrapper,newLat.wrapper,newLon.wrapper);
          const editActions=document.createElement("div");editActions.className="tf-card-actions";
          const save=document.createElement("button");save.type="button";
          save.className="tf-save";save.textContent="Gem ændringer";
          save.addEventListener("click",async()=>{
            const latitude=Number(newLat.input.value),longitude=Number(newLon.input.value);
            if(!newLat.input.value.trim()||!newLon.input.value.trim()||
               !Number.isFinite(latitude)||!Number.isFinite(longitude)){
              this.message("Indtast gyldige koordinater.",true);return;
            }
            save.disabled=true;
            await call("PUT",{shared_id:place.id,name:newName.input.value.trim(),
              latitude,longitude},"Fælles sted opdateret.");
            save.disabled=false;
          });
          const remove=document.createElement("button");remove.type="button";
          remove.className="tf-save";remove.textContent="Slet sted";
          remove.style.background="var(--error-color,#b3261e)";
          remove.addEventListener("click",async()=>{
            if(!window.confirm("Slet dette fælles sted for alle familiemedlemmer?"))return;
            remove.disabled=true;
            await call("DELETE",{shared_id:place.id},"Fælles sted slettet.");
            remove.disabled=false;
          });
          editActions.append(save,remove);edit.appendChild(editActions);
          card.appendChild(edit);
        }
        sharedList.appendChild(card);
      }
      if(!sharedList.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen fælles steder endnu. Opret det første ovenfor.";
        sharedList.appendChild(empty);
      }
      for(const place of data.places||[]){
        const card=document.createElement("section");card.className="tf-person";
        const heading=document.createElement("strong");
        heading.textContent=place.name+" · "+(place.status==="suggested"?"Forslag":"Ophold");
        const info=document.createElement("p");
        info.textContent=place.visits+" besøg · "+place.minutes+" minutter";
        const actions=document.createElement("div");actions.className="tf-card-actions";
        const publish=document.createElement("button");publish.type="button";
        publish.className="tf-save";publish.textContent="Del med familien";
        publish.addEventListener("click",()=>fill(place));
        actions.append(publish,openMaps(place));
        card.append(heading,info,actions);
        ownList.appendChild(card);
      }
      if(!ownList.children.length){
        const empty=document.createElement("p");
        empty.textContent="Der er endnu ingen indlærte ophold.";
        ownList.appendChild(empty);
      }
      if(data.can_manage_all_places){
        if(!adminDetails.isConnected)root.appendChild(adminDetails);
        for(const place of data.admin_suggestions||[]){
          const card=document.createElement("section");card.className="tf-person";
          const heading=document.createElement("strong");
          heading.textContent=place.person_name+" · "+place.name;
          const info=document.createElement("p");
          info.textContent=place.visits+" besøg · "+place.minutes+" minutter"+
            (place.last?" · sidst "+place.last:"");
          const actions=document.createElement("div");actions.className="tf-card-actions";
          const publish=document.createElement("button");publish.type="button";
          publish.className="tf-save";publish.textContent="Opret fælles sted";
          publish.addEventListener("click",()=>fill(place));
          const zone=document.createElement("button");zone.type="button";
          zone.className="tf-save";zone.textContent="Opret HA-zone";
          zone.addEventListener("click",async()=>{
            const named=window.prompt("Navn på zonen",place.name==="Ukendt sted"?"":place.name);
            if(named===null||!named.trim())return;
            const radiusText=window.prompt("Zonens radius i meter (25–5000)","100");
            if(radiusText===null)return;
            const radius=Number(radiusText);
            if(!Number.isInteger(radius)||radius<25||radius>5000){
              this.message("Vælg en radius mellem 25 og 5000 meter.",true);return;
            }
            zone.disabled=true;
            await call("POST",{person:place.person,name:named.trim(),radius,
              latitude:place.latitude,longitude:place.longitude},"Home Assistant-zone oprettet.");
            zone.disabled=false;
          });
          const rename=document.createElement("button");rename.type="button";
          rename.className="tf-save";rename.textContent="Ret stednavn";
          rename.addEventListener("click",async()=>{
            const named=window.prompt("Ret navn for "+place.person_name,place.name==="Ukendt sted"?"":place.name);
            if(named===null||!named.trim())return;
            rename.disabled=true;
            await call("PUT",{person:place.person,name:named.trim(),
              latitude:place.latitude,longitude:place.longitude},"Opholdssted opdateret.");
            rename.disabled=false;
          });
          actions.append(publish,zone,rename);
          card.append(heading,info,actions);
          adminList.appendChild(card);
        }
        if(!adminList.children.length)adminList.textContent="Ingen registrerede destinationer endnu.";
      }else if(adminDetails.isConnected)adminDetails.remove();
    };
    position.addEventListener("click",async()=>{
      position.disabled=true;
      try{
        const status=await this.hassInstance.callApi("GET","tiny_family/status");
        const own=(status.people||[]).find(item=>item.person===status.viewer_person);
        if(!own || own.stale || own.gps_health!=="fresh" ||
           !Number.isFinite(own.latitude)||!Number.isFinite(own.longitude)){
          this.message("Ingen frisk GPS-position fra din valgte telefon.",true);return;
        }
        choose(own.latitude,own.longitude);
      }catch(error){this.message("Kunne ikke hente din GPS-position.",true);}
      finally{position.disabled=false;}
    });
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      const latitude=Number(lat.value),longitude=Number(lon.value);
      if(!lat.value.trim()||!lon.value.trim()||
         !Number.isFinite(latitude)||!Number.isFinite(longitude)||
         latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180){
        this.message("Vælg først stedet på kortet eller indtast gyldige koordinater.",true);
        return;
      }
      submit.disabled=true;
      if(await call("POST",{kind:"shared",name:name.value.trim(),
           latitude,longitude},"Fælles sted er oprettet for hele familien.")){
        name.value="";
      }
      submit.disabled=false;
    });
    try{await load();}
    catch(error){this.message("Steder kunne ikke indlæses: "+this.errorText(error),true);}
  }

  async routes(root) {
    const title=document.createElement("h2");title.textContent="Familieruter – seneste 24 timer";
    root.appendChild(title);
    const info=document.createElement("p");info.className="tf-message";
    info.textContent="Kun delbare GPS-spor vises. Historiske privatmarkerede spor beskyttes fortsat. Kortfliser kan hentes fra OpenStreetMap.";
    root.appendChild(info);
    const tools=document.createElement("div");tools.className="tf-fields";
    const people=document.createElement("select");
    people.setAttribute("aria-label","Vis ruter for person");
    const everyone=document.createElement("option");
    everyone.value="";everyone.textContent="Alle tilgængelige personer";people.appendChild(everyone);
    const hours=document.createElement("select");
    hours.setAttribute("aria-label","Tidsrum");
    for(const n of [1,6,12,24]){
      const option=document.createElement("option");
      option.value=String(n);option.textContent="Seneste "+n+" timer";
      hours.appendChild(option);
    }
    hours.value="24";
    tools.append(people,hours);root.appendChild(tools);
    const mapNode=document.createElement("div");
    mapNode.className="tf-map";mapNode.style.marginTop="12px";
    root.appendChild(mapNode);
    const report=document.createElement("p");
    report.className="tf-message";root.appendChild(report);
    const refresh=document.createElement("button");
    refresh.type="button";refresh.className="tf-save";
    refresh.textContent="Opdater ruter";root.appendChild(refresh);
    let routeData=null, names={},health={};
    const draw=async()=>{
      try{
        if(!routeData){
          const [routes,status]=await Promise.all([
            this.hassInstance.callApi("GET","tiny_family/routes"),
            this.hassInstance.callApi("GET","tiny_family/status")
          ]);
          routeData=routes;
          names=Object.fromEntries((status.people||[]).map(p=>[p.person,p.name]));
          health=Object.fromEntries((status.people||[]).map(p=>[p.person,p]));
          const wasSelected=people.value;
          people.replaceChildren(everyone);
          for(const row of routes.paths||[]){
            const option=document.createElement("option");
            option.value=row.person;option.textContent=names[row.person]||row.person;
            people.appendChild(option);
          }
          const wanted=this._routeFilterPerson||wasSelected;
          if([...people.options].some(p=>p.value===wanted))people.value=wanted;
          this._routeFilterPerson=null;
        }
        const L=await this.leaflet();
        if(this.active!=="routes")return;
        if(this._familyMap){this._familyMap.remove();this._familyMap=null;}
        const map=this.createLeafletMap(mapNode);
        await this.addBaseMap(map,mapNode);
        const bounds=[],now=Date.now()/1000,since=now-Number(hours.value)*3600;
        let count=0;
        for(const row of routeData.paths||[]){
          if(people.value && row.person!==people.value)continue;
          for(const segment of row.segments||[]){
            const pts=segment.filter(p=>Array.isArray(p)&&p.length===3 &&
                            Number.isFinite(p[0])&&Number.isFinite(p[1])&&
                            Number.isFinite(p[2])&&p[2]>=since);
            if(!pts.length)continue;
            if(pts.length>1){
              L.polyline(pts.map(p=>[p[0],p[1]]),{
                color:"#389ab8",weight:4,opacity:0.88
              }).addTo(map);
            }
            L.circleMarker([pts[pts.length-1][0],pts[pts.length-1][1]],{
              radius:5,color:"#157c9b"
            }).bindTooltip(names[row.person]||row.person).addTo(map);
            bounds.push(...pts.map(p=>[p[0],p[1]]));
            count+=pts.length;
          }
        }
        if(bounds.length)map.fitBounds(bounds,{padding:[35,35],maxZoom:15});
        else map.setView([this.hassInstance.config.latitude||0,
                          this.hassInstance.config.longitude||0],5);
        const selected=(routeData.paths||[]).filter(p=>!people.value||p.person===people.value);
        const gpsStatus=selected.map(p=>{
          const state=health[p.person]||{};
          const label=state.stale?"forældet":state.gps_health==="fresh"?"frisk":"ukendt";
          const age=state.updated_at?Math.max(0,Math.round((Date.now()-Date.parse(state.updated_at))/60000)):null;
          return (names[p.person]||p.person)+": "+label+
            (Number.isFinite(age)?" ("+age+" min)":"");
        });
        const gaps=selected.reduce((total,p)=>
          total+Math.max(0,(p.segments||[]).length-1),0);
        report.textContent=(count?"Viser "+count+" GPS-punkter.":"Ingen delbare spor i det valgte tidsrum. Kontroller GPS, tidsrummet og Ghost Mode.")+
          (gaps?" · "+gaps+" adskilte rutestykker/GPS-pauser.":"")+
          (gpsStatus.length?" · GPS-status: "+gpsStatus.join("; ")+".":"")+
          " Spor er historiske, ikke en garanti for aktuel position.";
        setTimeout(()=>{if(this._familyMap===map)map.invalidateSize();},120);
      }catch(error){report.textContent="Ruter kunne ikke indlæses: "+error.message;}
    };
    people.addEventListener("change",draw);
    hours.addEventListener("change",draw);
    refresh.addEventListener("click",()=>{
      routeData=null;draw();
    });
    await draw();
  }

  async family(root) {
    const heading=document.createElement("h2");heading.textContent="Familiekort";root.appendChild(heading);
    const help=document.createElement("p");help.className="tf-message";
    help.textContent="Her ser du familiens positioner, fælles steder og ruter. Forældede GPS-positioner markeres særskilt.";
    root.appendChild(help);
    const routesLabel=document.createElement("label");
    routesLabel.className="tf-message";
    const routesToggle=document.createElement("input");
    routesToggle.type="checkbox";routesToggle.checked=true;
    routesLabel.append(routesToggle,
      document.createTextNode(" Vis delte ruter fra de seneste 24 timer"));
    root.appendChild(routesLabel);
    const routeFilters=document.createElement("div");
    routeFilters.className="tf-fields";
    const hoursLabel=document.createElement("label");
    hoursLabel.textContent="Rutehistorik";
    const routeHours=document.createElement("select");
    for(const hours of [1,6,12,24]){
      const option=document.createElement("option");
      option.value=String(hours);option.textContent="Sidste "+hours+" timer";
      routeHours.appendChild(option);
    }
    routeHours.value="24";hoursLabel.appendChild(routeHours);
    const personRouteLabel=document.createElement("label");
    personRouteLabel.textContent="Person på rute";
    const routePerson=document.createElement("select");
    const allRoutes=document.createElement("option");
    allRoutes.value="";allRoutes.textContent="Alle delte personer";
    routePerson.appendChild(allRoutes);
    personRouteLabel.appendChild(routePerson);
    routeFilters.append(hoursLabel,personRouteLabel);
    root.appendChild(routeFilters);
    const zonesLabel=document.createElement("label");
    zonesLabel.className="tf-message";
    const zonesToggle=document.createElement("input");
    zonesToggle.type="checkbox";zonesToggle.checked=true;
    zonesLabel.append(zonesToggle,document.createTextNode(" Vis geografiske zoner og deres radius"));
    root.appendChild(zonesLabel);
    const polygonLabel=document.createElement("label");
    polygonLabel.className="tf-message";
    const polygonsToggle=document.createElement("input");
    polygonsToggle.type="checkbox";polygonsToggle.checked=true;
    polygonLabel.append(polygonsToggle,
      document.createTextNode(" Vis Tiny Family-polygonområder"));
    root.appendChild(polygonLabel);
    const zoneInfo=document.createElement("p");
    zoneInfo.className="tf-message";
    zoneInfo.textContent="Zoner vises som geografiske cirkler. Home Assistant-områder (rum/enheder) har ingen kortgrænser.";
    root.appendChild(zoneInfo);
    let selectedZoneCenter=null;
    const zoneEditor=document.createElement("form");
    zoneEditor.className="tf-person";
    zoneEditor.style.display="none";
    const zoneHeading=document.createElement("strong");
    zoneHeading.textContent="Administrator: opret geografisk zone";
    const zoneName=document.createElement("input");
    zoneName.required=true;zoneName.maxLength=80;
    zoneName.placeholder="Zonenavn (fx Skole eller Træning)";
    zoneName.setAttribute("aria-label","Zonenavn");
    const zoneRadius=document.createElement("input");
    zoneRadius.type="number";zoneRadius.min="25";zoneRadius.max="5000";
    zoneRadius.required=true;zoneRadius.value="100";
    zoneRadius.setAttribute("aria-label","Zoneradius i meter");
    const zoneLocation=document.createElement("span");
    zoneLocation.textContent="Tryk på kortet for at vælge zonens centrum. Radius angives i meter.";
    const zoneSave=document.createElement("button");
    zoneSave.type="submit";zoneSave.className="tf-save";
    zoneSave.textContent="Gem som Home Assistant-zone";
    const storedLabel=document.createElement("label");
    storedLabel.textContent="Eksisterende, redigerbar zone";
    const storedZones=document.createElement("select");
    const emptyZone=document.createElement("option");
    emptyZone.value="";emptyZone.textContent="Opret ny zone";
    storedZones.appendChild(emptyZone);
    storedLabel.appendChild(storedZones);
    const deleteZone=document.createElement("button");
    deleteZone.type="button";deleteZone.className="tf-save";
    deleteZone.style.background="var(--error-color,#ad3131)";
    deleteZone.textContent="Slet valgt zone";
    deleteZone.disabled=true;
    storedZones.addEventListener("change",()=>{
      const selected=[...storedZones.options].find(o=>o.value===storedZones.value);
      deleteZone.disabled=!storedZones.value;
      zoneSave.textContent=storedZones.value?"Gem zoneændringer":"Opret ny zone";
      if(!selected || !storedZones.value){
        selectedZoneCenter=null;
        zoneLocation.textContent="Tryk på kortet for at vælge zonens centrum.";
        return;
      }
      const zone=JSON.parse(selected.dataset.zone);
      selectedZoneCenter={lat:Number(zone.latitude),lon:Number(zone.longitude)};
      zoneName.value=zone.name;zoneRadius.value=String(zone.radius);
      zoneLocation.textContent="Kortcentrum valgt fra "+zone.name+
        ". Tryk på kortet for at flytte zonen.";
    });
    zoneEditor.append(zoneHeading,storedLabel,zoneName,zoneRadius,zoneLocation,zoneSave,deleteZone);
    root.appendChild(zoneEditor);
    zoneEditor.addEventListener("submit",async event=>{
      event.preventDefault();
      if(!selectedZoneCenter){this.message("Vælg først centrum ved at trykke på kortet.",true);return;}
      zoneSave.disabled=true;
      try{
        await this.hassInstance.callApi(
          storedZones.value?"PUT":"POST","tiny_family/zones",{
            ...(storedZones.value?{zone_id:storedZones.value}:{}),
            name:zoneName.value.trim(),
            latitude:selectedZoneCenter.lat,longitude:selectedZoneCenter.lon,
            radius:Number(zoneRadius.value)
          }
        );
        zoneName.value="";storedZones.value="";
        deleteZone.disabled=true;zoneSave.textContent="Opret ny zone";
        selectedZoneCenter=null;
        zoneLocation.textContent="Zone gemt. Vælg et nyt centrum på kortet.";
        this.message("Zonen er oprettet i Home Assistant.");
        await draw();
      }catch(error){this.message("Kunne ikke oprette zone: "+error.message,true);}
      finally{zoneSave.disabled=false;}
    });
    deleteZone.addEventListener("click",async()=>{
      if(!storedZones.value)return;
      const zoneNameToDelete=zoneName.value;
      if(!window.confirm("Slet zonen '"+zoneNameToDelete+"' fra Home Assistant? Dette kan ikke fortrydes."))return;
      deleteZone.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/zones",{
          zone_id:storedZones.value,confirm:true
        });
        storedZones.value="";zoneName.value="";
        selectedZoneCenter=null;zoneSave.textContent="Opret ny zone";
        this.message("Zonen er slettet i Home Assistant.");
        await draw();
      }catch(error){
        this.message("Kunne ikke slette zonen: "+error.message,true);
      }finally{deleteZone.disabled=!storedZones.value;}
    });
    // Polygon geofences are managed independently of circular HA zones.
    let drawingPolygon=false;
    let polygonPoints=[];
    const polygonEditor=document.createElement("form");
    polygonEditor.className="tf-person";
    polygonEditor.style.display="none";
    const polygonHeading=document.createElement("strong");
    polygonHeading.textContent="Administrator: polygonområder (3–32 hjørner)";
    const polygonChoice=document.createElement("select");
    const polygonNew=document.createElement("option");
    polygonNew.value="";polygonNew.textContent="Opret nyt polygonområde";
    polygonChoice.appendChild(polygonNew);
    const polygonName=document.createElement("input");
    polygonName.required=true;polygonName.maxLength=80;
    polygonName.placeholder="Navn på området";
    const polygonHint=document.createElement("span");
    polygonHint.className="tf-message";
    polygonHint.textContent="Vælg Tegn, og tryk mindst tre steder på kortet.";
    const polygonDraw=document.createElement("button");
    polygonDraw.type="button";polygonDraw.className="tf-save";
    polygonDraw.textContent="Start polygontegning";
    polygonDraw.addEventListener("click",()=>{
      drawingPolygon=!drawingPolygon;
      if(drawingPolygon)polygonPoints=[];
      polygonDraw.textContent=drawingPolygon?"Afslut tegning":"Start polygontegning";
      polygonHint.textContent=drawingPolygon
        ?"Tryk på kortet for hvert hjørne. Maks. 32 hjørner."
        :"Området har "+polygonPoints.length+" hjørner.";
    });
    const polygonSave=document.createElement("button");
    polygonSave.type="submit";polygonSave.className="tf-save";
    polygonSave.textContent="Gem polygon";
    const polygonDelete=document.createElement("button");
    polygonDelete.type="button";polygonDelete.className="tf-save";
    polygonDelete.textContent="Slet polygon";
    polygonDelete.style.background="var(--error-color,#ad3131)";
    polygonDelete.disabled=true;
    polygonChoice.addEventListener("change",()=>{
      const selected=polygonChoice.selectedOptions[0];
      polygonDelete.disabled=!polygonChoice.value;
      const item=selected?.dataset?.item ? JSON.parse(selected.dataset.item) : null;
      polygonName.value=item?.name || "";
      polygonPoints=item?.points ? item.points.map(p=>[p[0],p[1]]) : [];
      drawingPolygon=false;polygonDraw.textContent="Start polygontegning";
      polygonHint.textContent=item
        ?"Eksisterende polygon med "+polygonPoints.length+" hjørner. Tegn igen for at ændre formen."
        :"Vælg Tegn og sæt mindst tre hjørner på kortet.";
    });
    polygonEditor.append(
      polygonHeading,polygonChoice,polygonName,polygonHint,
      polygonDraw,polygonSave,polygonDelete
    );
    root.appendChild(polygonEditor);
    polygonEditor.addEventListener("submit",async event=>{
      event.preventDefault();
      if(polygonPoints.length<3){
        this.message("Tegn mindst tre polygonhjørner på kortet.",true);return;
      }
      polygonSave.disabled=true;
      try{
        await this.hassInstance.callApi(
          polygonChoice.value?"PUT":"POST","tiny_family/geofences",{
            ...(polygonChoice.value?{id:polygonChoice.value}:{}),
            name:polygonName.value.trim(),points:polygonPoints
          });
        this.message("Polygonområdet er gemt i Tiny Family.");
        polygonName.value="";polygonPoints=[];drawingPolygon=false;
        polygonChoice.value="";polygonDraw.textContent="Start polygontegning";
        await draw();
      }catch(error){this.message("Polygon blev ikke gemt: "+error.message,true);}
      finally{polygonSave.disabled=false;}
    });
    polygonDelete.addEventListener("click",async()=>{
      if(!polygonChoice.value)return;
      if(!window.confirm("Slet polygonområdet '"+polygonName.value+"' permanent?"))return;
      polygonDelete.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/geofences",{
          id:polygonChoice.value,confirm:true
        });
        polygonChoice.value="";polygonName.value="";polygonPoints=[];
        this.message("Polygonområdet er slettet.");
        await draw();
      }catch(error){this.message("Polygon kunne ikke slettes: "+error.message,true);}
      finally{polygonDelete.disabled=!polygonChoice.value;}
    });
    const toolsPanel=document.createElement("details");
    toolsPanel.className="tf-map-tools";
    const toolsTitle=document.createElement("summary");
    toolsTitle.textContent="Kortlag og avancerede kortværktøjer";
    toolsPanel.appendChild(toolsTitle);
    for(const element of [help,routesLabel,routeFilters,zonesLabel,polygonLabel,
                          zoneInfo,zoneEditor,polygonEditor]){
      toolsPanel.appendChild(element);
    }
    root.appendChild(toolsPanel);
    const mapElement=document.createElement("div");
    mapElement.className="tf-map";mapElement.style.marginBottom="15px";
    root.insertBefore(mapElement,toolsPanel);
    const list=document.createElement("div");list.className="tf-fields";root.appendChild(list);
    const refresh=document.createElement("button");refresh.className="tf-save";
    refresh.textContent="Opdater personer";
    root.appendChild(refresh);
    let drawing=false;
    let previousSignature="";
    const draw=async()=>{
      if(drawing || this.active!=="live" || !this.isConnected)return;
      drawing=true;
      refresh.disabled=true;
      try {
        const data=await this.hassInstance.callApi("GET","tiny_family/status");
        if (this.active!=="live") return;
        this._viewerPerson=data.viewer_person;
        const polygonData=await this.hassInstance.callApi("GET","tiny_family/geofences");
        if(this.active!=="live")return;
        const previousRoutePerson=routePerson.value;
        routePerson.replaceChildren(allRoutes);
        for(const person of data.people || []){
          if(person.ghost && person.person!==data.viewer_person)continue;
          const option=document.createElement("option");
          option.value=person.person;option.textContent=person.name;
          routePerson.appendChild(option);
        }
        routePerson.value=[...routePerson.options].some(
          o=>o.value===previousRoutePerson)?previousRoutePerson:"";
        const signature=JSON.stringify({
          people:data.people,zones:data.zones,polygons:polygonData.geofences,
          routes:routesToggle.checked,routeHours:routeHours.value,
          routePerson:routePerson.value,
          zoneVisibility:zonesToggle.checked,
          polygonVisibility:polygonsToggle.checked
        });
        if(signature===previousSignature && this._familyMap)return;
        previousSignature=signature;
        zoneEditor.style.display=data.can_manage_zones?"grid":"none";
        polygonEditor.style.display=polygonData.editable?"grid":"none";
        if(polygonData.editable){
          const oldValue=polygonChoice.value;
          polygonChoice.replaceChildren(polygonNew);
          for(const polygon of polygonData.geofences || []){
            const option=document.createElement("option");
            option.value=polygon.id;option.textContent=polygon.name;
            option.dataset.item=JSON.stringify(polygon);
            polygonChoice.appendChild(option);
          }
          polygonChoice.value=[...polygonChoice.options].some(p=>p.value===oldValue)
            ?oldValue:"";
          polygonDelete.disabled=!polygonChoice.value;
        }
        if(data.can_manage_zones){
          const stored = await this.hassInstance.callApi("GET","tiny_family/zones");
          const previous=storedZones.value;
          storedZones.replaceChildren(emptyZone);
          for(const zone of stored.zones || []){
            const opt=document.createElement("option");
            opt.value=zone.id;opt.textContent=zone.name;
            opt.dataset.zone=JSON.stringify(zone);
            storedZones.appendChild(opt);
          }
          storedZones.value=[...storedZones.options].some(o=>o.value===previous)
            ?previous:"";
          deleteZone.disabled=!storedZones.value;
        }
        list.replaceChildren();
        await this.leaflet();
        if(this._familyMap) {this._familyMap.remove();this._familyMap=null;}
        const map=this.createLeafletMap(mapElement);
        if(data.can_manage_zones){
          let draft=null, polygonDraft=null;
          map.on("click",event=>{
            if(drawingPolygon){
              if(polygonPoints.length>=32){
                this.message("Maksimalt 32 polygonhjørner.",true);return;
              }
              polygonPoints.push([event.latlng.lat,event.latlng.lng]);
              polygonHint.textContent=polygonPoints.length+
                " hjørner registreret. Tegn videre eller gem polygonen.";
              if(polygonDraft)polygonDraft.remove();
              if(polygonPoints.length>=3){
                polygonDraft=window.L.polygon(polygonPoints,{
                  color:"#9c56c4",fillOpacity:0.13,weight:2,dashArray:"4 5"
                }).addTo(map);
              }else{
                polygonDraft=window.L.polyline(polygonPoints,{
                  color:"#9c56c4",weight:2,dashArray:"4 5"
                }).addTo(map);
              }
              return;
            }
            selectedZoneCenter={lat:event.latlng.lat,lon:event.latlng.lng};
            zoneLocation.textContent="Valgt centrum: "+
              selectedZoneCenter.lat.toFixed(5)+", "+
              selectedZoneCenter.lon.toFixed(5)+
              " · Radius "+zoneRadius.value+" m";
            if(draft)draft.remove();
            draft=window.L.circle(
              [selectedZoneCenter.lat,selectedZoneCenter.lon],
              {radius:Number(zoneRadius.value)||100,color:"#ff9900",weight:2,
               fillColor:"#ff9900",fillOpacity:0.15}
            ).addTo(map);
          });
        }
        await this.addBaseMap(map,mapElement);
        const bounds=[];
        const zoneBounds=[];
        if(polygonsToggle.checked){
          for(const polygon of polygonData.geofences || []){
            if(!Array.isArray(polygon.points)||polygon.points.length<3)continue;
            const shape=window.L.polygon(polygon.points,{
              color:"#9c56c4",weight:2,fillColor:"#9c56c4",fillOpacity:0.10
            }).addTo(map);
            shape.bindTooltip(polygon.name);
            zoneBounds.push(polygon.points[0]);
          }
        }
        // Shared places are an explicitly published collection, not private GPS history.
        const sharedData=await this.hassInstance.callApi("GET","tiny_family/places")
          .catch(()=>({shared_places:[]}));
        for(const place of sharedData.shared_places||[]){
          if(!Number.isFinite(place.latitude)||!Number.isFinite(place.longitude))continue;
          const marker=window.L.circleMarker([place.latitude,place.longitude],{
            radius:7,color:"#ffffff",weight:2,fillColor:"#9c56c4",fillOpacity:1
          }).addTo(map);
          const label=document.createElement("span");
          label.textContent=place.name;
          marker.bindPopup(label);
          zoneBounds.push([place.latitude,place.longitude]);
        }
        if(routesToggle.checked){
          const routes=await this.hassInstance.callApi("GET","tiny_family/routes");
          if(this.active!=="live")return;
          const since=Date.now()/1000-Number(routeHours.value)*3600;
          for(const person of routes.paths || []){
            if(routePerson.value && person.person!==routePerson.value)continue;
            const color=this.settings.colors?.[person.person] || "#00a8a9";
            for(const segment of person.segments || []){
              const selected=segment.filter(p=>p[2]>=since);
              if(selected.length<2)continue;
              window.L.polyline(selected.map(p=>[p[0],p[1]]),{
                color,weight:4,opacity:0.7
              }).addTo(map);
            }
          }
        }
        if(zonesToggle.checked){
          for(const zone of data.zones || []){
            if(!Number.isFinite(zone.latitude) || !Number.isFinite(zone.longitude) ||
               !Number.isFinite(zone.radius_m) || zone.radius_m <= 0)continue;
            const center=[zone.latitude,zone.longitude];
            const circle=window.L.circle(center,{
              radius:zone.radius_m,color:"#548fe2",weight:2,
              fillColor:"#548fe2",fillOpacity:0.08
            }).addTo(map);
            const label=document.createElement("span");
            label.textContent=zone.name+" · "+Math.round(zone.radius_m)+" m";
            circle.bindTooltip(label);
            zoneBounds.push(center);
          }
        }
        for(const person of data.people || []){
          const box=document.createElement("section");box.className="tf-person";
          const head=document.createElement("div");head.className="tf-card-head";
          const title=document.createElement("strong");title.textContent=person.name;
          const liveLabel=document.createElement("span");liveLabel.className="tf-chip";
          liveLabel.textContent=person.ghost?"Ghost Mode – skjult":
            person.stale?"GPS forældet":person.gps_health==="fresh"?"Frisk GPS":"GPS ukendt";
          head.append(title,liveLabel);box.appendChild(head);
          const status=document.createElement("p");
          status.textContent=person.ghost ? "Ghost Mode – position skjult" :
            (person.status || "Ukendt")+" · "+(person.stale?"sidste position":"opdateret")+
            (person.battery_percent!=null?" · "+person.battery_percent+" % batteri":"")+
            (person.charging==="on"?" · oplader":"")+
            (person.activity && person.activity!=="unknown"?" · "+person.activity:"");
          box.appendChild(status);
          if(!person.ghost && person.stale){
            const warning=document.createElement("p");
            warning.className="tf-message";
            warning.textContent="Ingen frisk GPS-position. Ruter og ankomsttider er historiske eller utilgængelige.";
            box.appendChild(warning);
          }
          if(person.updated_at && !person.ghost){
            const stamp=document.createElement("small");
            const date=new Date(person.updated_at);
            stamp.textContent=Number.isNaN(date.getTime())?""
              :"Sidste registrerede GPS-fix: "+date.toLocaleString("da-DK")+
                (Number.isFinite(person.gps_age_minutes)?
                  " ("+person.gps_age_minutes+" min siden)":"");
            box.appendChild(stamp);
          }
          if(person.home_eta_minutes && !person.ghost && !person.stale){
            const homeEta=document.createElement("span");
            homeEta.textContent="På vej hjem · anslået "+person.home_eta_minutes+" min (GPS-estimat)";
            box.appendChild(homeEta);
          }
          if(person.destination && !person.ghost && !person.stale){
            const eta=document.createElement("span");
            eta.textContent="Mulig destination: "+person.destination+
              (person.eta_minutes ? " · ETA "+person.eta_minutes+" min" : "")+
              (person.destination_confidence ?
                 " · sikkerhed ca. "+person.destination_confidence+" %" : "");
            box.appendChild(eta);
          }
          if(Number.isFinite(person.latitude) && Number.isFinite(person.longitude) && !person.ghost){
            const point=[person.latitude,person.longitude];
            const battery=person.battery_percent;
            const color=person.stale?"#888888":battery!=null&&battery<20?"#d64646":
              battery!=null&&battery<=50?"#d79b3f":"#1fb77e";
            const circle=window.L.circleMarker(point,{radius:11,color:"#ffffff",weight:2,
              fillColor:color,fillOpacity:0.95}).addTo(map);
            circle.bindPopup(person.name);
            bounds.push(point);
            if(!person.stale){
              const navigate=document.createElement("a");
              navigate.href="https://www.google.com/maps/dir/?api=1&destination="+
                encodeURIComponent(person.latitude+","+person.longitude);
              navigate.target="_blank";navigate.rel="noopener noreferrer";
              navigate.textContent="Naviger til personen";
              box.appendChild(navigate);
            }
          }
          const cardActions=document.createElement("div");
          cardActions.className="tf-card-actions";
          const goRoute=document.createElement("button");
          goRoute.type="button";goRoute.className="tf-save";
          goRoute.textContent="Vis rute";goRoute.disabled=person.ghost && person.person!==data.viewer_person;
          goRoute.addEventListener("click",()=>{
            this._routeFilterPerson=person.person;this.show("routes");
          });
          cardActions.appendChild(goRoute);
          if(person.person!==data.viewer_person){
            const write=document.createElement("button");
            write.type="button";write.className="tf-save";
            write.textContent="Skriv besked";
            write.addEventListener("click",()=>{
              this._composeRecipient=person.person;this.show("contact");
            });
            cardActions.appendChild(write);
          }
          box.appendChild(cardActions);
          list.appendChild(box);
        }
        if(!list.children.length){
          const empty=document.createElement("p");empty.className="tf-empty";
          empty.textContent="Ingen tilknyttede familiemedlemmer endnu. Tilknyt personer og HA-brugere i Administration.";
          list.appendChild(empty);
        }
        if(bounds.length)map.fitBounds(bounds,{padding:[35,35],maxZoom:15});
        else if(zoneBounds.length)map.fitBounds(zoneBounds,{padding:[35,35],maxZoom:14});
        else map.setView([this.hassInstance.config.latitude||0,
                           this.hassInstance.config.longitude||0],5);
        setTimeout(()=>map.invalidateSize(),150);
      }catch(error){this.message("Familiekort kunne ikke indlæses: "+error.message,true);}
      finally{refresh.disabled=false;drawing=false;}
    };
    refresh.addEventListener("click",()=>{previousSignature="";draw();});
    zonesToggle.addEventListener("change",()=>{previousSignature="";draw();});
    polygonsToggle.addEventListener("change",()=>{previousSignature="";draw();});
    routesToggle.addEventListener("change",()=>{previousSignature="";draw();});
    routeHours.addEventListener("change",()=>{previousSignature="";draw();});
    routePerson.addEventListener("change",()=>{previousSignature="";draw();});
    await draw();
    this._familyTimer=setInterval(()=>{
      if(this.active==="live" && this.isConnected)draw();
    },30000);
  }

  async today(root) {
    const heading = document.createElement("h2");
    heading.textContent = "Min dag";
    root.appendChild(heading);
    const info = document.createElement("p");
    info.className = "tf-message";
    root.appendChild(info);
    const sharing=document.createElement("section");sharing.className="tf-person";
    root.appendChild(sharing);
    const trackingTitle=document.createElement("strong");
    trackingTitle.textContent="Sporing via din telefon";
    const trackingNote=document.createElement("p");trackingNote.className="tf-message";
    trackingNote.textContent="Din valgte Home Assistant Companion-telefon leverer GPS, batteri, opladning og aktivitet. Hvis telefonen ikke sender data, vises de som utilgængelige.";
    sharing.append(trackingTitle,trackingNote);
    const routineLabel=document.createElement("label");
    const routineCheckbox=document.createElement("input");
    routineCheckbox.type="checkbox";
    routineLabel.append(routineCheckbox,document.createTextNode(
      " Lær mine typiske afgangstider lokalt (valgfrit)"));
    sharing.appendChild(routineLabel);
    const routineNote=document.createElement("p");
    routineNote.className="tf-message";
    routineNote.textContent="Læring kræver administratorens aktivering og dit personlige samtykke. Tidspunkter gemmes lokalt i op til 60 dage og kan være synlige for andre HA-brugere via HA-sensorer. Slår du fra, slettes mine mønsterdata.";
    sharing.appendChild(routineNote);
    const permissions=document.createElement("section");
    permissions.className="tf-person";
    const permissionsTitle=document.createElement("strong");
    permissionsTitle.textContent="Hvem kan se mine data?";
    const permissionsBody=document.createElement("div");
    permissions.append(permissionsTitle,permissionsBody);
    sharing.appendChild(permissions);
    const refreshPermissions=async()=>{
      try{
        const policy=await this.hassInstance.callApi("GET","tiny_family/sharing");
        const mine=policy.mine;
        permissionsBody.replaceChildren();
        if(!mine){permissionsBody.textContent="Din konto mangler en personbinding.";return;}
        const lines=[
          ["Position og 24-timers ruter",mine.ghost_active
            ?"Skjult i Tiny Family for andre":"Delt med: "+(mine.tiny_family_location_viewers.join(", ")||"ingen tilknyttede familiemedlemmer")],
          ["Systemhændelser",mine.ghost_active?"Privat i Tiny Family":
            "Synlige for familiemedlemmer med adgang"],
          ["Lærte steder og turarkiv","Kun min indloggede konto"],
          ["Beskeder","Kun afsender og konfigurerede modtagere"],
          ["Privat historik fra ældre opsætning",mine.ghost_active
            ?"Historiske privatmarkerede data er fortsat beskyttet":"Ingen"],
          ["Pushmodtagere",(mine.configured_phone_recipients||[]).join(", ")||"Ingen"],
        ];
        for(const [name,value] of lines){
          const line=document.createElement("p");
          const label=document.createElement("strong");label.textContent=name+": ";
          line.append(label,document.createTextNode(value));
          permissionsBody.appendChild(line);
        }
        const caveat=document.createElement("p");
        caveat.className="tf-message";
        caveat.textContent="GPS indsamles kun, når Companion-appen og telefonens tilladelser gør det muligt. Home Assistants øvrige adgangsrettigheder og Recorder administreres separat.";
        permissionsBody.appendChild(caveat);
      }catch(error){permissionsBody.textContent="Delingsoversigten kunne ikke indlæses.";}
    };
    routineCheckbox.addEventListener("change", async()=>{
      routineCheckbox.disabled=true;
      try {
        const value=await this.hassInstance.callApi("POST","tiny_family/privacy",{
          learn_my_routines:routineCheckbox.checked
        });
        routineCheckbox.checked=value.learn_my_routines;
        this.message("Min rutineindlæring "+(value.learn_my_routines?"aktiveret":"deaktiveret"));
      }catch(error){
        routineCheckbox.checked=!routineCheckbox.checked;
        this.message("Rutineindlæring kunne ikke ændres: "+error.message,true);
      }finally{routineCheckbox.disabled=false;}
    });
    try{
      const privacy=await this.hassInstance.callApi("GET","tiny_family/privacy");
      routineCheckbox.checked=privacy.learn_my_routines===true;
      routineCheckbox.disabled=!privacy.routine_learning_available;
      if(!privacy.routine_learning_available){
        routineNote.textContent="Administrator skal først aktivere lokal rutineindlæring i Administration.";
      }
    }catch(error){sharing.remove();}
    if(sharing.isConnected)await refreshPermissions();
    const personalData=document.createElement("section");
    personalData.className="tf-person";
    const personalTitle=document.createElement("strong");
    personalTitle.textContent="Mine lokalt gemte data";
    const personalIntro=document.createElement("p");
    personalIntro.textContent="Slet dine GPS-spor, indlærte steder eller afgangsmønstre. Dette sletter ikke Home Assistants Recorder-historik.";
    const choices={};
    for(const [key,label] of [
      ["routes","GPS-spor (24 timer)"],
      ["activities","Tur- og opholdsarkiv (30 dage)"],
      ["places","Indlærte opholdssteder"],
      ["routines","Indlærte afgangsmønstre (samtykke slås også fra)"]
    ]){
      const row=document.createElement("label");
      const checked=document.createElement("input");
      checked.type="checkbox";choices[key]=checked;
      row.append(checked,document.createTextNode(" "+label));
      personalData.appendChild(row);
    }
    const erase=document.createElement("button");
    erase.type="button";erase.className="tf-save";
    erase.style.background="var(--error-color,#a52d2d)";
    erase.textContent="Slet valgte personlige data";
    erase.addEventListener("click",async()=>{
      const categories=Object.keys(choices).filter(k=>choices[k].checked);
      if(!categories.length){this.message("Vælg først de data, du vil slette.",true);return;}
      if(!window.confirm("Slet de valgte Tiny Family-data permanent? Dette kan ikke fortrydes."))return;
      erase.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/personal_data",{
          categories,confirm:true
        });
        for(const input of Object.values(choices))input.checked=false;
        this.message("De valgte personlige data er slettet.");
        await this.hassInstance.callApi("GET","tiny_family/personal_data");
      }catch(error){this.message("Sletning fejlede: "+error.message,true);}
      finally{erase.disabled=false;}
    });
    personalData.prepend(personalTitle,personalIntro);
    personalData.appendChild(erase);
    const exportButton=document.createElement("button");
    exportButton.type="button";exportButton.className="tf-save";
    exportButton.textContent="Eksportér mine Tiny Family-data (JSON)";
    exportButton.addEventListener("click",async()=>{
      exportButton.disabled=true;
      try {
        const data=await this.hassInstance.callApi("GET","tiny_family/export");
        const blob=new Blob([JSON.stringify(data,null,2)],{
          type:"application/json"
        });
        const url=URL.createObjectURL(blob);
        const a=document.createElement("a");
        a.href=url;a.download="tiny-family-personal-export.json";
        a.style.display="none";document.body.appendChild(a);
        a.click();a.remove();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
        this.message("Din personlige eksport er klargjort. Filen indeholder private positionsdata.");
      }catch(error){this.message("Eksport mislykkedes: "+error.message,true);}
      finally{exportButton.disabled=false;}
    });
    personalData.appendChild(exportButton);
    root.appendChild(personalData);
    const recentArchive=document.createElement("section");
    recentArchive.className="tf-person";
    const recentTitle=document.createElement("strong");
    recentTitle.textContent="Seneste afsluttede ture og ophold";
    const recentBody=document.createElement("div");
    recentArchive.append(recentTitle,recentBody);
    root.appendChild(recentArchive);
    try{
      const archive=await this.hassInstance.callApi("GET","tiny_family/activity");
      for(const item of (archive.entries||[]).slice(0,5)){
        const line=document.createElement("p");
        line.textContent=(item.kind==="trip"?"Tur":"Ophold")+" · "+
          new Date(item.ended_at*1000).toLocaleString("da-DK")+" · "+
          item.duration_min+" min"+
          (item.kind==="trip"?" · "+item.distance_km+" km":"");
        recentBody.appendChild(line);
      }
      if(!recentBody.children.length)recentBody.textContent="Ingen afsluttede ture eller ophold endnu.";
    }catch(error){recentBody.textContent="Arkivet er ikke tilgængeligt endnu.";}
    const values = document.createElement("div");
    values.className = "tf-metrics";
    // Show live status first on mobile instead of putting settings before it.
    root.insertBefore(values,sharing);
    const extraDetails=document.createElement("details");
    extraDetails.className="tf-person tf-advanced";
    const extraTitle=document.createElement("summary");
    extraTitle.textContent="Flere aktivitets- og turdetaljer";
    const extraMetrics=document.createElement("div");
    extraMetrics.className="tf-metrics";
    extraDetails.append(extraTitle,extraMetrics);
    root.insertBefore(extraDetails,sharing);
    const primaryMetrics=new Set([
      "place","battery","charging","activity","speed",
      "gpsHealth","gpsAge","homeEta"
    ]);
    try {
      const data = await this.hassInstance.callApi("GET","tiny_family/communications");
      if (this.active !== "today") return;
      this._todayPerson = data.person;
      const entity = this.hassInstance.states[data.person];
      info.textContent = (entity?.attributes?.friendly_name || data.person) +
        " · personlig status fra Home Assistant Companion";
      for(const [key,label] of [
        ["place","Placering"], ["battery","Batteri"],
        ["charging","Opladning"], ["activity","Telefonaktivitet"],
        ["movement","Bevægelse"], ["distance","Distance i dag"],
        ["distanceWeek","Distance i denne uge"], ["stays","Ophold i dag"],
        ["currentStay","Aktuelt ophold"], ["lastTrip","Sidste tur"],
        ["speed","Aktuel hastighed"], ["maxSpeed","Maks. hastighed i dag"],
        ["destination","Destination"], ["eta","Anslået ankomst"],
        ["homeEta","Anslået hjemkomst"],
        ["usualDeparture","Typisk afgang"], ["gpsHealth","GPS-status"],
        ["gpsAge","Minutter siden GPS"], ["updated","Sidste opdatering"]
      ]) {
        const row = document.createElement("section");
        row.className = "tf-stat";
        const title = document.createElement("strong");title.textContent = label;
        const value = document.createElement("span");
        value.dataset.todayMetric = key;
        row.append(title,value);
        (primaryMetrics.has(key)?values:extraMetrics).appendChild(row);
      }
      try {
        const own=await this.hassInstance.callApi("GET","tiny_family/status");
        this._todayPrivateProfile=(own.people||[]).find(item=>item.person===data.person)||null;
      }catch(error){this._todayPrivateProfile=null;}
      this.updateToday();
    } catch (error) {
      info.textContent = "Din konto skal først knyttes til en person i Administration. " +
        (error.message || String(error));
    }
  }

  updateToday() {
    if (!this._todayPerson || this.active !== "today") return;
    const person = this._todayPerson;
    const all = this.hassInstance.states;
    const slug = person.slice("person.".length);
    const current = all[person];
    const state = key => {
      const value = all["sensor.person_timeline_"+slug+"_"+key]?.state;
      return (!value || ["unknown","unavailable"].includes(value)) ? "—" : value;
    };
    const units = (value,unit) => value==="—" ? "—" : value+" "+unit;
    const batteryEntity = this.settings?.batteries?.[person];
    const batteryState = batteryEntity && all[batteryEntity]?.state;
    const values = {
      place: current?.state || "—",
      battery: batteryState != null ? batteryState+" %" : "Ikke tilknyttet",
      charging: all["binary_sensor.person_timeline_"+slug+"_charging"]?.state==="on"
        ? "Oplader" : all["binary_sensor.person_timeline_"+slug+"_charging"]?.state==="off"
        ? "Ikke tilsluttet" : "—",
      activity: state("activity"),
      movement: state("gps_health")==="fresh" ? state("movement") : "—",
      distance: units(state("distance_today"),"km"),
      distanceWeek: units(state("distance_week"),"km"),
      stays: state("stays_today"),
      currentStay: units(state("current_stay"),"min"),
      lastTrip: state("last_trip"),
      speed: state("gps_health")==="fresh"
        ? units(state("current_speed"),"km/t") : "—",
      maxSpeed: units(state("max_speed"),"km/t"),
      destination: state("gps_health")==="fresh" ? state("destination") : "—",
      eta: state("gps_health")==="fresh" && state("destination")!=="Ingen"
        ? units(state("destination_eta"),"min") : "—",
      homeEta: state("gps_health")==="fresh"
        ? units(state("home_eta"),"min") : "—",
      usualDeparture: this._todayPrivateProfile?.usual_departure || "—",
      gpsHealth: ({fresh:"Frisk",stale:"Forældet",unknown:"Afventer GPS"})[
        state("gps_health")] || "Afventer GPS",
      gpsAge: units(state("gps_age_minutes"),"min"),
      updated: current?.last_updated ?
        new Date(current.last_updated).toLocaleString("da-DK") : "Ingen opdatering",
    };
    this.querySelectorAll("[data-today-metric]").forEach(element =>
      element.textContent = values[element.dataset.todayMetric] || "—");
  }

  async activity(root) {
    const heading=document.createElement("h2");
    heading.textContent="Mine ture og ophold";root.appendChild(heading);
    const note=document.createElement("p");note.className="tf-message";
    note.textContent="Arkivet indeholder afsluttede ture og ophold fra højst 30 dage. Kun din egen konto kan se det. GPS-kortspor gemmes i højst 24 timer.";
    root.appendChild(note);
    const routeButton=document.createElement("button");
    routeButton.className="tf-save";routeButton.type="button";
    routeButton.textContent="Se egne og delte GPS-spor på rutekortet";
    routeButton.addEventListener("click",()=>this.show("routes"));
    root.appendChild(routeButton);
    const list=document.createElement("div");root.appendChild(list);
    try {
      const data=await this.hassInstance.callApi("GET","tiny_family/activity");
      if(this.active!=="activity")return;
      if(data.trip_active){
        const active=document.createElement("section");
        active.className="tf-person";
        active.textContent="En tur er i gang. Den vises først her, når afslutningen er registreret.";
        list.appendChild(active);
      }
      for(const item of data.entries||[]){
        const card=document.createElement("section");card.className="tf-person";
        const title=document.createElement("strong");
        const fmt=t=>new Date(t*1000).toLocaleString("da-DK");
        title.textContent=(item.kind==="trip"?"Tur":"Ophold")+" · "+
          fmt(item.started_at)+" – "+fmt(item.ended_at);
        const body=document.createElement("p");
        const metrics=item.kind==="trip"
          ?item.distance_km+" km · maks. "+item.max_speed_kmh+" km/t"
          :(item.label||"Ukendt sted");
        body.textContent=item.duration_min+" min · "+metrics+
          (item.gps_gap?" · GPS-afbrydelse":"")+
          (item.private?" · registreret under Ghost Mode":"");
        card.append(title,body);list.appendChild(card);
      }
      if(!list.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen afsluttede ture eller ophold endnu. Afbrudte GPS-spor vises som afbrudte ture, når der er oplysninger nok.";
        list.appendChild(empty);
      }
    }catch(error){list.textContent="Turarkivet kunne ikke indlæses: "+error.message;}
  }

  async history(root) {
    const heading=document.createElement("h2");
    heading.textContent="Systemhistorik";root.appendChild(heading);
    const intro=document.createElement("p");intro.className="tf-message";
    intro.textContent="Hændelser fra familien vises kun, når positionen deles med dig. Gamle globale poster uden ejer vises ikke.";
    root.appendChild(intro);
    const filterLabel=document.createElement("label");
    filterLabel.className="tf-person";
    filterLabel.textContent="Vis hændelser";
    const typeFilter=document.createElement("select");
    typeFilter.setAttribute("aria-label","Filtrér systemhistorik efter alarm");
    for(const [value,label] of [
      ["all","Alle hændelser"],["zones","Ankomst og afgang"],
      ["speed","Fartadvarsler"],["battery","Batteriadvarsler"],
      ["gps","GPS og forbindelse"],["trip","Afsluttede ture"],
      ["weekly","Ugerapporter"],["other","Øvrige hændelser"]
    ]){
      const opt=document.createElement("option");opt.value=value;opt.textContent=label;
      typeFilter.appendChild(opt);
    }
    filterLabel.appendChild(typeFilter);root.appendChild(filterLabel);
    const infoLabel=document.createElement("p");
    infoLabel.className="tf-message";
    infoLabel.textContent="Systemhistorikken dokumenterer, at Tiny Family registrerede en hændelse. Den er ikke en kvittering for, at Home Assistant eller telefonen modtog en pushnotifikation. Fartalarmer bygger på GPS-data og kan være upræcise.";
    root.appendChild(infoLabel);
    const list=document.createElement("div");root.appendChild(list);
    let entries=[];
    const types={
      zone_arrived:"zones",zone_departed:"zones",
      speed_warning:"speed",battery_low:"battery",
      tracking_stale:"gps",tracking_restored:"gps",
      trip_ended:"trip",weekly_summary:"weekly",
    };
    const showHistory=()=>{
      list.replaceChildren();
      const selected=typeFilter.value;
      for(const item of entries){
        const category=types[item.event_key]||
          (/fart/i.test(item.kategori||"")?"speed":
           /batteri/i.test(item.kategori||"")?"battery":
           /ankomst|afgang/i.test(item.kategori||"")?"zones":
           /gps/i.test(item.kategori||"")?"gps":
           /tur/i.test(item.kategori||"")?"trip":
           /uge/i.test(item.kategori||"")?"weekly":"other");
        if(selected!=="all" && selected!==category)continue;
        const section=document.createElement("section");section.className="tf-person";
        const head=document.createElement("div");head.className="tf-card-head";
        const title=document.createElement("strong");
        title.textContent=(item.kategori||"Hændelse")+" · "+(item.tid||"");
        const label=document.createElement("span");label.className="tf-chip";
        label.textContent=({zones:"Zone",speed:"Fart",battery:"Batteri",
          gps:"GPS",trip:"Tur",weekly:"Uge",other:"Hændelse"})[category];
        head.append(title,label);
        const body=document.createElement("p");body.textContent=item.tekst||"";
        section.append(head,body);list.appendChild(section);
      }
      if(!list.children.length){
        const empty=document.createElement("p");empty.className="tf-empty";
        empty.textContent="Ingen hændelser i den valgte kategori.";
        list.appendChild(empty);
      }
    };
    typeFilter.addEventListener("change",showHistory);
    const clear=document.createElement("button");
    clear.type="button";clear.textContent="Ryd min systemhistorik";
    clear.className="tf-save";root.appendChild(clear);
    const load=async()=>{
      try{
        const data=await this.hassInstance.callApi("GET","tiny_family/history");
        if(this.active!=="history")return;
        entries=Array.isArray(data.entries)?data.entries:[];
        showHistory();
      }catch(error){
        list.textContent="Historikken er ikke tilgængelig: "+error.message;
        clear.disabled=true;
      }
    };
    clear.addEventListener("click",async()=>{
      if(!window.confirm("Skjul alle synlige systemhændelser i din egen historik?"))return;
      clear.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/history");
        await load();
      }catch(error){this.message("Rydning fejlede: "+error.message,true);}
      finally{clear.disabled=false;}
    });
    await load();
  }

  help(root) {
    const title = document.createElement("h2");
    title.textContent = "Hjælp til Tiny Family";
    root.appendChild(title);
    const items = [
      ["Kom i gang", "Opret først personer i Home Assistant, og forbind telefonerne med Companion-appen."],
      ["Administration", "Kun administratorer ser fanen Administration. Vælg person, Home Assistant-bruger og Companion-telefon; batteri, opladning og aktivitet hentes fra samme telefon, når sensorerne er registreret."],
      ["Min dag", "Viser den indloggede persons status fra Home Assistant. Manglende eller gamle data bliver ikke gættet."],
      ["Check-in", "Giver andre tilknyttede personer besked om, at du er okay. En frisk position kan medtages."],
      ["På vej hjem", "Sender en frivillig besked. ETA beregnes kun, når hastighed og position er tilstrækkelige."],
      ["SOS", "Sender en hjælpanmodning til de konfigurerede telefoner. Dette er ikke en alarmcentral eller en erstatning for 112."],
      ["Beskedstatus", "Accepteret betyder, at Home Assistants notifikationstjeneste tog imod anmodningen, ikke at telefonen har modtaget beskeden. Læsekvittering kræver, at modtageren markerer beskeden som læst inde i Tiny Family. Ved netværksfejl skal du bekræfte et eventuelt nyt forsøg, da det kan give en dobbeltbesked."],
      ["Automatiske alarmer", "Administrator bestemmer pr. familiemedlem hvilke ankomst-, afgangs-, fart-, batteri- og GPS-advarsler der er aktive. Systemhistorikken viser registrerede hændelser, ikke bekræftet push-levering."],
      ["GPS og sporing", "GPS-sporing styres via den valgte Companion-telefon. Tiny Family har ingen pause- eller Ghost-knap. Hvis telefonens GPS-tilladelse mangler, vises data som gamle eller utilgængelige."],
      ["Android-widget", "Opret en Action Button-widget i Home Assistant Companion: handling = Kald tjeneste. Vælg person_timeline.mobile_checkin, person_timeline.mobile_heading_home eller person_timeline.mobile_sos."],
      ["iPhone og iPad", "Brug Home Assistant Companion-genveje eller en iOS-Genvej, der kalder de tilsvarende Tiny Family-tjenester med den indloggede brugers konto."],
      ["Svar direkte fra push", "Ved en Companion notify.mobile_app_*-modtager kan du skrive svar på telefonens notifikation. Svarnøglen gælder én gang i højst 24 timer og udløber ved HA-genstart/genindlæsning. Andre notify-enheder har almindelige beskeder uden hurtigsvar."],
      ["Position ved beskeder", "Check-in, På vej hjem og SOS kan medtage en frisk GPS-position fra den valgte Companion-telefon. Almindelige fritekstbeskeder vedhæfter ikke GPS automatisk. Tidligere privatindstillinger fra gamle installationer bevares indtil migration."],
      ["Læsekvittering", "Modtageren kan trykke Markér som læst i Tiny Familys beskedhistorik. Dette bekræfter kun en handling inde i panelet, ikke at en pushbesked blev vist eller læst på telefonen."],
      ["Automatiske beskeder", "Aktivér kun efter valg af personer, konti og telefonmodtagere i Administration. Batteri- og fartadvarsler kræver passende Companion-sensorer."],
      ["Rutinegenkendelse", "Valgfri lokal læring af typiske afgangstider. Resultatet bruges kun efter mindst tre sammenlignelige afgangstider."],
      ["Privatliv", "Hver bruger kan kun se sin egen beskedhistorik i Tiny Family. Der er stadig selvstændige Home Assistant-rettigheder til andre entiteter."],
    ];
    items.push(["GPS-datakvalitet", "Når telefonen ikke har sendt et GPS-fix i 15 minutter, markeres data som forældede. Aktive ture og bevægelsesstatus nulstilles uden at opfinde en afsluttet tur. Eventuelle GPS-advarsler aktiveres separat i Administration."]);
    for(const [heading,body] of items) {
      const box = document.createElement("section");box.className="tf-person";
      const h = document.createElement("strong");h.textContent=heading;
      const p = document.createElement("p");p.textContent=body;
      box.append(h,p);root.appendChild(box);
    }
    const mobile=document.createElement("section");
    mobile.className="tf-person";
    const mobileTitle=document.createElement("h3");
    mobileTitle.textContent="Companion-handlinger til telefonen";
    mobile.appendChild(mobileTitle);
    const guide=document.createElement("p");
    guide.textContent="Tilføj en Action Button-widget i Companion på Android, vælg Kald tjeneste og indsæt én af tjenesterne. Slå gerne Kræv godkendelse til for SOS.";
    mobile.appendChild(guide);
    for(const [name,entity] of [
      ["Check-in", "person_timeline.mobile_checkin"],
      ["På vej hjem", "person_timeline.mobile_heading_home"],
      ["SOS", "person_timeline.mobile_sos"],
      ["Besked", "person_timeline.mobile_message"]
    ]) {
      const line=document.createElement("div");line.className="tf-fields";
      const code=document.createElement("code");
      code.textContent=name+": "+entity;line.appendChild(code);
      const copy=document.createElement("button");copy.type="button";
      copy.textContent="Kopiér tjeneste";
      copy.addEventListener("click",async()=>{
        try {
          await navigator.clipboard.writeText(entity);
          copy.textContent="Kopieret";
        }catch(error){this.message("Kopiér tjenesten manuelt: "+entity,true);}
      });
      line.appendChild(copy);mobile.appendChild(line);
    }
    const slug=this._viewerPerson?.startsWith("person.")
      ? this._viewerPerson.slice("person.".length):"din_person";
    const examples=[
      ["Android: Entity State-widget","sensor.person_timeline_"+slug+"_movement"],
      ["Android: GPS-fix alder","sensor.person_timeline_"+slug+"_gps_age_minutes"],
      ["Android: opladningsstatus","binary_sensor.person_timeline_"+slug+"_charging"],
      ["Android: destination","sensor.person_timeline_"+slug+"_destination"],
      ["Android: Template-widget",
       "{{ states('sensor.person_timeline_"+slug+"_distance_today') }} km · "+
       "{{ states('sensor.person_timeline_"+slug+"_movement') }}"],
      ["iOS: Open Page / sidepanel","/tiny-family"]
    ];
    const mobileMore=document.createElement("h3");
    mobileMore.textContent="Flere Companion-widgets og genveje";
    mobile.appendChild(mobileMore);
    const mobileInfo=document.createElement("p");
    mobileInfo.textContent="Android: Tilføj en Home Assistant Companion-widget på telefonens startskærm og vælg Entity State eller Template. iOS: Brug Companion-widgeten Open Page eller en Genvej, som åbner /tiny-family. Kopiér værdierne herunder.";
    mobile.appendChild(mobileInfo);
    for(const [label,value] of examples){
      const wrapper=document.createElement("section");
      wrapper.className="tf-person";
      const title=document.createElement("strong");title.textContent=label;
      const content=document.createElement("code");
      content.textContent=value;
      const button=document.createElement("button");
      button.type="button";button.textContent="Kopiér";
      button.addEventListener("click",async()=>{
        try{await navigator.clipboard.writeText(value);button.textContent="Kopieret";}
        catch(error){this.message("Kopiér værdien manuelt: "+value,true);}
      });
      wrapper.append(title,content,button);mobile.appendChild(wrapper);
    }
    const limitation=document.createElement("p");
    limitation.className="tf-message";
    limitation.textContent="Telefonens widgets og systemtilladelser oprettes ikke automatisk. Det kræver handling i den officielle Companion-app på hver telefon.";
    mobile.appendChild(limitation);
    root.appendChild(mobile);
  }

  async contact(root) {
    const heading = document.createElement("h2");
    heading.textContent = "Beskeder og sikkerhed";
    root.appendChild(heading);
    const info = document.createElement("p");
    info.textContent = "Send beskeder, check-in og SOS gennem Home Assistants tilknyttede notifikationstjenester. En accepteret notifikation er ikke bevis for, at den er leveret på telefonen. En læsekvittering kræver, at modtageren åbner Tiny Family og aktivt markerer beskeden som læst.";
    root.appendChild(info);

    const note = document.createElement("p");
    note.className = "tf-message";
    note.setAttribute("role", "status");
    root.appendChild(note);
    const form = document.createElement("form");
    form.className = "tf-person";
    const input = document.createElement("textarea");
    input.maxLength = 500; input.rows = 3;
    input.placeholder = "Skriv en besked ...";
    input.setAttribute("aria-label","Besked");
    input.style.cssText = "width:100%;box-sizing:border-box;padding:10px;font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:10px";
    form.appendChild(input);
    const includePositionLabel=document.createElement("label");
    const includePositionCheckbox=document.createElement("input");
    includePositionCheckbox.type="checkbox";
    includePositionCheckbox.checked=true;
    includePositionLabel.append(includePositionCheckbox,document.createTextNode(
      " Medtag position ved Check-in, På vej hjem og SOS, hvis tilladt under Min dag"));
    form.appendChild(includePositionLabel);
    const recipientLabel = document.createElement("label");
    recipientLabel.textContent = "Send besked til";
    const recipientSelect = document.createElement("select");
    recipientSelect.setAttribute("aria-label", "Beskedmodtager");
    const everyone = document.createElement("option");
    everyone.value = "";everyone.textContent = "Hele familien";
    recipientSelect.appendChild(everyone);
    recipientLabel.appendChild(recipientSelect);
    form.appendChild(recipientLabel);
    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;flex-wrap:wrap;gap:8px";
    const ids = [
      ["message","Send besked"], ["checkin","Check-in: Jeg er okay"],
      ["heading_home","På vej hjem"], ["sos","SOS – bed om hjælp"]
    ];
    const buttons = [];
    const deliveryDetails=document.createElement("section");
    deliveryDetails.className="tf-person";
    deliveryDetails.setAttribute("aria-label","Beskedstatus");
    const deliveryLegend=document.createElement("p");
    deliveryLegend.className="tf-message";
    deliveryLegend.textContent="1. Accepteret: Home Assistant-notifikationstjenesten har modtaget anmodningen. 2. Leveret: telefonens faktiske modtagelse kan ikke bekræftes. 3. Læst: kun når modtageren aktivt markerer beskeden som læst i Tiny Family.";
    deliveryDetails.appendChild(deliveryLegend);
    const retry=document.createElement("button");
    retry.type="button";retry.className="tf-save";
    retry.textContent="Prøv sidste afsendelse igen";
    retry.hidden=true;
    let retryPayload=null;
    const setRetry=(payload)=>{
      retryPayload=payload;
      retry.hidden=!payload;
    };
    const send=async(payload)=>{
      buttons.forEach(b=>b.button.disabled=true);
      retry.disabled=true;
      note.textContent="Sender anmodning til Home Assistant…";
      try {
        const result=await this.hassInstance.callApi("POST","tiny_family/communications",payload);
        const accepted=Number(result.recipients_sent)||0;
        const failed=Number(result.recipients_failed)||0;
        const positionText=result.location_status==="included"?" · Frisk position medtaget.":
          result.location_status==="unavailable"?" · Ingen frisk GPS: sendt uden position.":
          result.location_status==="withheld"?" · Position udeladt efter dine privatlivsvalg.":"";
        note.textContent="HA-notifikationstjenesten accepterede "+accepted+
          " af "+(Number(result.attempted_recipients)||accepted+failed)+
          " modtager(e)."+(failed?" "+failed+" kunne ikke accepteres.":"")+
          positionText+" Telefonlevering kan ikke verificeres. En læsekvittering kræver handling i Tiny Family.";
        setRetry(null);
        if(payload.action==="message" && accepted>0 && input.value===payload.message)input.value="";
        try{await loadHistory();}catch(historyError){
          note.textContent+=" Beskedhistorikken kunne ikke opdateres.";
        }
      }catch(error){
        note.textContent="Afsendelsen blev ikke bekræftet: "+this.errorText(error)+
          " Tekst og modtagervalg er bevaret. Ved netværksfejl kan anmodningen allerede være accepteret.";
        const code=error?.body?.error_code||error?.error_code;
        setRetry(["invalid_action","invalid_recipient","not_linked"].includes(code)?null:payload);
      }finally{
        buttons.forEach(b=>b.button.disabled=false);
        retry.disabled=false;
      }
    };
    retry.addEventListener("click",async()=>{
      if(!retryPayload)return;
      if(!window.confirm("Forsøger du igen, kan modtageren få beskeden to gange, hvis det forrige svar gik tabt. Vil du sende på ny?"))return;
      const payload={...retryPayload};
      setRetry(null);
      await send(payload);
    });
    for (const [action,title] of ids) {
      const button=document.createElement("button");
      button.type="button";button.className="tf-save";
      button.textContent=title;
      if(action==="sos")button.style.background="var(--error-color,#c62828)";
      actions.appendChild(button);buttons.push({button,action});
      button.addEventListener("click",async()=>{
        if(action==="sos" && !window.confirm(
          "Send en SOS-hjælpanmodning? Tiny Family er ikke en nødopkaldstjeneste. Positionen medtages kun hvis den er frisk og tilladt."))return;
        const payload={
          action,message:action==="message"?input.value:"",
          include_location:includePositionCheckbox.checked,
          ...(action==="message" && recipientSelect.value?
              {recipient_person:recipientSelect.value}:{})
        };
        setRetry(null);
        await send(payload);
      });
    }
    form.appendChild(actions);
    deliveryDetails.appendChild(retry);
    form.appendChild(deliveryDetails);
    const shortcuts=document.createElement("div");
    shortcuts.style.cssText="display:flex;gap:6px;flex-wrap:wrap";
    for(const phrase of ["👋 Hej", "📍 Hvor er du?", "🚗 På vej", "🏡 Er snart hjemme", "📞 Ring til mig"]){
      const shortcut=document.createElement("button");
      shortcut.type="button";shortcut.textContent=phrase;
      shortcut.style.cssText="padding:7px 10px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);border-radius:10px";
      shortcut.addEventListener("click",()=>{input.value=phrase;input.focus();});
      shortcuts.appendChild(shortcut);
    }
    form.appendChild(shortcuts);root.appendChild(form);
    recipientSelect.addEventListener("change",()=>{
      for(const {button,action} of buttons){
        if(action==="message")button.disabled=false;
      }
    });
    const warning = document.createElement("p");
    warning.className="tf-message";
    warning.textContent="SOS er en frivillig beskedfunktion, ikke en certificeret alarmtjeneste eller erstatning for 112.";
    root.appendChild(warning);
    const title = document.createElement("h3");title.textContent="Din beskedhistorik";root.appendChild(title);
    const history = document.createElement("div");root.appendChild(history);
    const clear=document.createElement("button");
    clear.type="button";clear.textContent="Ryd min beskedvisning";
    clear.style.cssText="margin-top:12px;color:var(--error-color);border:1px solid var(--divider-color);background:transparent;padding:10px;border-radius:10px";
    root.appendChild(clear);
    clear.addEventListener("click",async()=>{
      if(!window.confirm("Vil du skjule alle beskeder i din egen historik? De andre deltagere beholder deres kopier."))return;
      clear.disabled=true;
      try{
        await this.hassInstance.callApi("DELETE","tiny_family/communications");
        note.textContent="Din beskedhistorik er ryddet.";
        await loadHistory();
      }catch(error){note.textContent="Kunne ikke rydde: "+error.message;}
      finally{clear.disabled=false;}
    });
    const loadHistory = async () => {
      try {
        const response = await this.hassInstance.callApi("GET","tiny_family/communications");
        const prior = recipientSelect.value;
        recipientSelect.replaceChildren(everyone);
        for (const person of response.recipients || []) {
          const option = document.createElement("option");
          option.value = person.person;option.textContent = person.name;
          recipientSelect.appendChild(option);
        }
        if ([...recipientSelect.options].some(option=>option.value===prior)) {
          recipientSelect.value = prior;
        }
        note.textContent = note.textContent || (response.recipients_configured ?
          "Klar til at kontakte "+response.recipients_configured+" tilknyttet(e) telefonmodtager(e)." :
          "Ingen andre telefonmodtagere er konfigureret. Administrator skal vælge Companion-modtagere i Administration.");
        if(this._composeRecipient){
          const chosen=this._composeRecipient;
          this._composeRecipient=null;
          if([...recipientSelect.options].some(option=>option.value===chosen)){
            recipientSelect.value=chosen;
            input.focus();
          }else{
            note.textContent="Den valgte person har ingen tilknyttet beskedmodtager. Kontakt administrator i Administration.";
            // Never fall back to 'everyone' when direct messaging was requested.
            recipientSelect.value="";
            for(const {button,action} of buttons){
              if(action==="message")button.disabled=true;
            }
          }
        }
        history.replaceChildren();
        for(const item of response.history || []) {
          const box = document.createElement("section");
          box.className = "tf-person";
          const label = document.createElement("strong");
          label.textContent = (item.kategori || "Besked") + " · " + (item.tid || "");
          const body = document.createElement("p");
          body.textContent = item.tekst || "";
          box.append(label,body);
          if(item.fra === response.person){
            const delivery=document.createElement("span");
            delivery.className="tf-chip";
            const accepted=item.accepted_recipients ?? item.recipient_count ?? 0;
            const rejected=item.failed_recipients ?? 0;
            delivery.textContent="HA accepterede "+accepted+
              (rejected?" · "+rejected+" fejlede":"")+
              " · Telefonlevering ukendt";
            box.appendChild(delivery);
          }
          if (item.fra === response.person && typeof item.recipient_count === "number") {
            const receipt = document.createElement("p");
            receipt.className="tf-message";
            receipt.textContent="Markeret som læst i Tiny Family: "+item.read_count+" af "+item.recipient_count+
              " modtagere (ikke telefonens pushkvittering).";
            box.appendChild(receipt);
          }
          if(item.fra !== response.person && item.id && !item.read_by_me) {
            const acknowledge = document.createElement("button");
            acknowledge.type="button";acknowledge.textContent="Markér som læst";
            acknowledge.className="tf-save";
            acknowledge.addEventListener("click", async()=>{
              acknowledge.disabled=true;
              try {
                await this.hassInstance.callApi("POST","tiny_family/communications",{
                  action:"acknowledge",message_id:item.id
                });
                await loadHistory();
              } catch(error) {
                note.textContent="Kunne ikke kvittere for læsning: "+(error.message||String(error));
                acknowledge.disabled=false;
              }
            });
            box.appendChild(acknowledge);
          } else if(item.fra !== response.person && item.read_by_me) {
            const read = document.createElement("span");
            read.className="tf-message";read.textContent="Markeret som læst i Tiny Family";
            box.appendChild(read);
          }
          if(item.fra && item.fra!==response.person &&
             [...recipientSelect.options].some(o=>o.value===item.fra)){
            const reply=document.createElement("button");
            reply.type="button";reply.textContent="Svar";
            reply.style.cssText="justify-self:start;padding:7px 14px;border:1px solid var(--divider-color);border-radius:10px;color:var(--primary-text-color);background:var(--card-background-color)";
            reply.addEventListener("click",()=>{
              recipientSelect.value=item.fra;
              input.focus();
              note.textContent="Svar sendes kun til "+item.fra+".";
            });
            box.appendChild(reply);
          }
          history.appendChild(box);
        }
        if(!history.children.length){
          const empty=document.createElement("p");empty.className="tf-empty";
          empty.textContent="Ingen beskeder endnu. Hvis du ikke kan sende, skal administrator tilknytte telefonmodtagere i Administration.";
          history.appendChild(empty);
        }
      } catch(error) {
        note.textContent = "Beskeder kunne ikke indlæses: "+this.errorText(error)+
          ". Kontroller din person- og telefonbinding i Administration.";
      }
    };
    await loadHistory();
  }

  editor(root) {
    if (!this.settings.editable) { root.textContent = "Kun administratorer kan ændre indstillinger."; return; }
    const adminHeading=document.createElement("div");adminHeading.className="tf-admin-head";
    const adminIcon=document.createElement("ha-icon");adminIcon.setAttribute("icon","mdi:shield-crown");
    const heading=document.createElement("h2");heading.textContent="Administration – Tiny Family";
    adminHeading.append(adminIcon,heading);root.appendChild(adminHeading);
    const info=document.createElement("p");info.className="tf-message";
    info.textContent="Administrationen samler familiens telefoner, notifikationer, fartgrænser og zoner. Vælg én Companion-telefon pr. person; dens registrerede sensorer tilknyttes automatisk.";
    root.appendChild(info);
    const zoneTools=document.createElement("button");
    zoneTools.type="button";zoneTools.className="tf-save";
    zoneTools.textContent="Åbn administratorværktøjer til zoner og polygoner på familiekortet";
    zoneTools.addEventListener("click",()=>this.show("live"));
    root.appendChild(zoneTools);
    const form = document.createElement("form");
    const autoLabel=document.createElement("label");
    autoLabel.className="tf-person";
    const autoNotifications=document.createElement("input");
    autoNotifications.type="checkbox";
    autoNotifications.checked=Boolean(this.settings.auto_notifications_enabled);
    autoLabel.append(autoNotifications,document.createTextNode(
      " Send automatisk ankomst-, batteri-, fart- og turalarmer til familiens tilknyttede telefoner"));
    form.appendChild(autoLabel);
    const alertCategoryNames = {
      zone_arrived:"Ankomst", zone_departed:"Afgang",
      battery_low:"Lavt batteri", speed_warning:"Høj fart",
      trip_ended:"Afsluttet tur", weekly_summary:"Ugerapport",
      tracking_stale:"GPS-opdatering mangler", tracking_restored:"GPS igen aktiv"
    };
    const enabledEvents = new Set(this.settings.notification_events || Object.keys(alertCategoryNames));
    const alertOptions = {};
    const categoryBox=document.createElement("section");
    categoryBox.className="tf-person";
    const categoryHeading=document.createElement("strong");
    categoryHeading.textContent="Vælg automatiske notifikationer";
    categoryBox.appendChild(categoryHeading);
    const alertHelp=document.createElement("p");
    alertHelp.className="tf-message";
    alertHelp.textContent="Notifikationer er frivillige og kræver en aktiv indstilling og en gyldig Companion-modtager. Fartadvarsler kræver to troværdige GPS-målinger over grænsen. Zoner kræver stabil position. Et registreret event er ikke en bekræftet pushlevering.";
    categoryBox.appendChild(alertHelp);
    for(const [key, label] of Object.entries(alertCategoryNames)){
      const labelElement=document.createElement("label");
      const checkbox=document.createElement("input");
      checkbox.type="checkbox";checkbox.checked=enabledEvents.has(key);
      alertOptions[key]=checkbox;
      labelElement.append(checkbox,document.createTextNode(" "+label));
      categoryBox.appendChild(labelElement);
    }
    form.appendChild(categoryBox);
    const speedLabel=document.createElement("label");
    speedLabel.className="tf-person";
    speedLabel.textContent="Fartgrænse for advarsel (km/t)";
    const speedLimit=document.createElement("input");
    speedLimit.type="number";speedLimit.min="30";speedLimit.max="200";speedLimit.step="1";
    speedLimit.required=true;
    speedLimit.value=String(this.settings.speed_limit_kmh ?? 130);
    speedLabel.appendChild(speedLimit);
    const speedHint=document.createElement("span");
    speedHint.className="tf-message";
    speedHint.textContent="Fælles standard. Hver person kan få egen grænse nedenfor. Advarsel kræver to troværdige GPS-målinger.";
    speedLabel.appendChild(speedHint);
    form.appendChild(speedLabel);
    const routinesLabel=document.createElement("label");
    routinesLabel.className="tf-person";
    const routineLearning=document.createElement("input");
    routineLearning.type="checkbox";
    routineLearning.checked=Boolean(this.settings.learn_routines_enabled);
    routinesLabel.append(routineLearning,document.createTextNode(
      " Tillad lokal rutineindlæring (hver person skal også give samtykke i Min dag; data slettes ved fravalg)"));
    form.appendChild(routinesLabel);
    const rows = [];
    for (const person of this.settings.available_persons || []) {
      const section = document.createElement("section");
      section.className = "tf-person";
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = (this.settings.persons || []).includes(person.id);
      label.append(checkbox, document.createTextNode(" " + person.name));
      section.appendChild(label);
      const fields = document.createElement("div");
      fields.className = "tf-fields";
      const choice = (name, items, current, container=fields) => {
        const wrap = document.createElement("label");
        wrap.appendChild(document.createTextNode(name));
        const select = document.createElement("select");
        const blank = document.createElement("option");
        blank.value = ""; blank.textContent = "Ingen / automatisk"; select.appendChild(blank);
        for (const item of items) {
          const option = document.createElement("option");
          option.value = item.id; option.textContent = item.name; select.appendChild(option);
        }
        select.value = current || "";
        wrap.appendChild(select);container.appendChild(wrap);
        return select;
      };
      const tracker = choice("Telefon (Home Assistant Companion / GPS)", this.settings.available_trackers || [], this.settings.trackers?.[person.id]);
      const detected=document.createElement("p");
      detected.className="tf-message";fields.appendChild(detected);
      // The selected Companion phone owns every sensor binding.
      // No independent battery/activity drop-downs: the backend resolves
      // them from the very same HA device registry entry.
      const battery={value:""},charging={value:""},activity={value:""};
      const refreshPhone=()=>{
        const auto=this.settings.device_sensors?.[tracker.value]||{};
        battery.value=auto.battery||"";
        charging.value=auto.charging||"";
        activity.value=auto.activity||"";
        const found=Object.keys(auto).filter(key=>auto[key]);
        detected.textContent=tracker.value
          ?found.length
            ?"Sensorer fra denne telefon: "+found.map(key=>({
               battery:"batteri",charging:"opladning",activity:"aktivitet"
              })[key]||key).join(", ")
            :"Ingen Companion-sensorer fundet på telefonen. Aktivér dem i Home Assistant Companion."
          :"Vælg telefonen én gang. GPS og tilgængelige sensorer tilknyttes automatisk.";
      };
      tracker.addEventListener("change",refreshPhone);
      refreshPhone();
      const colorLabel = document.createElement("label");colorLabel.textContent = "Farve";
      const color = document.createElement("input");color.type="color";color.value=this.settings.colors?.[person.id]||"#00a8a9";
      colorLabel.appendChild(color);fields.appendChild(colorLabel);
      section.append(fields);form.appendChild(section);
      const owner = choice("Home Assistant-bruger", this.settings.available_users || [],
                           this.settings.owners?.[person.id]);
      const target = choice("Companion push-modtager", this.settings.available_notify_targets || [],
                            this.settings.notification_targets?.[person.id]);
      const personSpeedLabel=document.createElement("label");
      personSpeedLabel.textContent="Personlig fartgrænse (km/t; tom = fælles)";
      const personSpeed=document.createElement("input");
      personSpeed.type="number";personSpeed.min="30";personSpeed.max="200";personSpeed.step="1";
      personSpeed.placeholder=String(this.settings.speed_limit_kmh ?? 130);
      personSpeed.value=String(this.settings.speed_limits_kmh?.[person.id] ?? "");
      personSpeedLabel.appendChild(personSpeed);fields.appendChild(personSpeedLabel);
      const personEventsBox=document.createElement("section");
      personEventsBox.className="tf-person";
      const useGlobalEvents=document.createElement("input");
      useGlobalEvents.type="checkbox";
      useGlobalEvents.checked=!Object.prototype.hasOwnProperty.call(
        this.settings.person_notification_events || {}, person.id);
      const inheritLabel=document.createElement("label");
      inheritLabel.append(useGlobalEvents,
          document.createTextNode(" Brug fælles notifikationsvalg"));
      personEventsBox.appendChild(inheritLabel);
      const individualEvents={};
      const ownEvents = new Set(this.settings.person_notification_events?.[person.id] ??
                                this.settings.notification_events ?? Object.keys(alertCategoryNames));
      for (const [eventName, eventLabel] of Object.entries(alertCategoryNames)) {
        const labelElement=document.createElement("label");
        const checked=document.createElement("input");
        checked.type="checkbox";checked.checked=ownEvents.has(eventName);
        checked.disabled=useGlobalEvents.checked;
        individualEvents[eventName]=checked;
        labelElement.append(checked,document.createTextNode(" "+eventLabel));
        personEventsBox.appendChild(labelElement);
      }
      useGlobalEvents.addEventListener("change",()=>{
        for (const checkbox of Object.values(individualEvents))
          checkbox.disabled=useGlobalEvents.checked;
      });
      fields.appendChild(personEventsBox);
      rows.push({person:person.id,checkbox,tracker,battery,charging,activity,color,
                 owner,target,personSpeed,useGlobalEvents,individualEvents,refreshPhone});
    }
    const migrateLabel=document.createElement("label");
    migrateLabel.className="tf-person";
    const migrateTitle=document.createElement("strong");
    migrateTitle.textContent="Overfør tidligere Tiny Family-opsætning";
    const migrateInfo=document.createElement("span");
    migrateInfo.textContent="Indlæs en lokal migrations-preview fra scripts/migration_preview.py. Intet gemmes før du gennemgår valgene og trykker Gem indstillinger.";
    const migrateFile=document.createElement("input");
    migrateFile.type="file";migrateFile.accept=".json,application/json";
    migrateLabel.append(migrateTitle,migrateInfo,migrateFile);
    form.appendChild(migrateLabel);
    const migrationReview=document.createElement("section");
    migrationReview.className="tf-person";migrationReview.style.display="none";
    const migrationHeading=document.createElement("strong");
    migrationHeading.textContent="Gennemgang af ældre funktioner og scripts";
    const migrationDetails=document.createElement("div");
    const migrationConfirm=document.createElement("label");
    const migrationReady=document.createElement("input");
    migrationReady.type="checkbox";
    migrationConfirm.append(migrationReady,document.createTextNode(
      " Jeg har lavet en fuld Home Assistant-backup og gennemgået de scripts, automationer og brugerbindinger, som kræver manuel migration."
    ));
    migrationReview.append(migrationHeading,migrationDetails,migrationConfirm);
    form.appendChild(migrationReview);
    let migrationPending=false;
    migrateFile.addEventListener("change",async()=>{
      const file=migrateFile.files?.[0];
      if(!file)return;
      try{
        if(file.size>1024*1024)throw new Error("Filen er for stor");
        const plan=JSON.parse(await file.text());
        if(plan?.format!=="tiny-family-migration-preview-v1" ||
           !plan.settings || !Array.isArray(plan.settings.persons)){
          throw new Error("Ugyldigt Tiny Family-migrationsformat");
        }
        const selected=new Set(plan.settings.persons);
        migrationPending=true;migrationReady.checked=false;
        migrationReview.style.display="grid";
        migrationDetails.replaceChildren();
        const summary=document.createElement("p");
        summary.textContent=(plan.script_review||[]).length+
          " identificerede scripts og "+(plan.automation_references_count||0)+
          " registrerede automationsreferencer. Ukendte !include-filer skal gennemgås særskilt.";
        migrationDetails.appendChild(summary);
        for(const feature of (plan.feature_coverage||[])){
          const line=document.createElement("p");
          line.textContent=feature.legacy+" → "+feature.new+
            " ("+(feature.mode==="built_in"?"findes i Tiny Family":
                    "kræver gennemgang")+")";
          migrationDetails.appendChild(line);
        }
        for(const script of (plan.script_review||[])){
          const line=document.createElement("p");
          line.textContent="Script "+script.id+" → forslag: "+
            script.possible_replacement+" (skal kontrolleres manuelt)";
          migrationDetails.appendChild(line);
        }
        for(const step of (plan.remaining_manual_steps||[])){
          const line=document.createElement("p");
          line.textContent="Kontrollér: "+step;
          migrationDetails.appendChild(line);
        }
        const known=new Set(rows.map(row=>row.person));
        const missing=[...selected].filter(p=>!known.has(p));
        for(const row of rows){
          row.checkbox.checked=selected.has(row.person);
          for(const [element,key] of [
            [row.tracker,"trackers"]
          ]){
            const value=plan.settings[key]?.[row.person];
            if(value && [...element.options].some(option=>option.value===value))
              element.value=value;
          }
          row.refreshPhone(false);
          const color=plan.settings.colors?.[row.person];
          if(typeof color==="string" && /^#[0-9a-fA-F]{6}$/.test(color))
            row.color.value=color;
        }
        this.message("Migreringsforslaget er indlæst. "+(
          missing.length?missing.length+" person(er) findes ikke i HA. ":"")+
          "Gennemgå brugere, telefonmodtagere og alarmregler før du gemmer.");
      }catch(error){
        this.message("Migrationsfilen blev afvist: "+error.message,true);
      }finally{migrateFile.value="";}
    });
    if (!rows.length) {
      const note = document.createElement("p");
      note.textContent = "Opret personer under Indstillinger → Personer i Home Assistant.";
      form.appendChild(note);
    }
    const save = document.createElement("button");
    save.type="submit";save.className="tf-save";save.textContent="Gem indstillinger";form.appendChild(save);
    form.addEventListener("submit",async e => {
      e.preventDefault();
      if(migrationPending && !migrationReady.checked){
        this.message("Bekræft først backup og manuel gennemgang af migrationen.",true);
        return;
      }
      save.disabled=true;this.message("Gemmer …");
      const persons=[],trackers={},batteries={},charging_sensors={},activity_sensors={},
            colors={},owners={},notification_targets={},
            speed_limits_kmh={},person_notification_events={};
      for(const row of rows) if(row.checkbox.checked) {
        persons.push(row.person);
        trackers[row.person]=row.tracker.value;
        batteries[row.person]=row.battery.value;
        charging_sensors[row.person]=row.charging.value;
        activity_sensors[row.person]=row.activity.value;
        colors[row.person]=row.color.value;
        if(row.owner.value) owners[row.person]=row.owner.value;
        if(row.target.value) notification_targets[row.person]=row.target.value;
        if(row.personSpeed.value!=="") speed_limits_kmh[row.person]=Number(row.personSpeed.value);
        if(!row.useGlobalEvents.checked){
          person_notification_events[row.person]=
            Object.keys(row.individualEvents).filter(k=>row.individualEvents[k].checked);
        }
      }
      try {
        await this.hassInstance.callApi("POST","tiny_family/settings",{
          persons,trackers,batteries,charging_sensors,activity_sensors,
          colors,owners,notification_targets,
          speed_limit_kmh:Number(speedLimit.value),
          speed_limits_kmh,person_notification_events,
          notification_events:Object.keys(alertOptions).filter(key=>alertOptions[key].checked),
          auto_notifications_enabled:autoNotifications.checked,
          learn_routines_enabled:routineLearning.checked
        });
        await this.refreshSettings();
        this.message("Ændringer gemt. Integrationen genindlæses.");
      } catch(error) { this.message("Kunne ikke gemme: "+error.message,true); }
      finally {save.disabled=false;}
    });
    root.appendChild(form);
    const permissions=document.createElement("section");
    permissions.className="tf-person";
    const headingPermissions=document.createElement("strong");
    headingPermissions.textContent="Administrator: deling og alarmer pr. person";
    permissions.appendChild(headingPermissions);
    const overview=document.createElement("div");
    permissions.appendChild(overview);
    root.appendChild(permissions);
    this.hassInstance.callApi("GET","tiny_family/sharing").then(policy=>{
      if(this.active!=="editor")return;
      overview.replaceChildren();
      for(const row of policy.family||[]){
        const item=document.createElement("p");
        const status=row.ghost_active?"Ghost aktiv":"Synlig";
        const people=row.tiny_family_location_viewers.join(", ")||"ingen";
        item.textContent=row.name+" · "+status+" · fartgrænse "+
          row.speed_alert_kmh+" km/t · Tiny Family-visning: "+people;
        overview.appendChild(item);
      }
      const note=document.createElement("p");
      note.className="tf-message";
      note.textContent="Oversigten viser gemte indstillinger. Formularens nye valg træder først i kraft, når du gemmer. Almindelige HA-entiteter og Recorder styres særskilt.";
      overview.appendChild(note);
    }).catch(error=>{
      overview.textContent="Delingsoversigten kunne ikke hentes: "+error.message;
    });
  }
}
customElements.define("tiny-family-panel", TinyFamilyPanel);
