#!/usr/bin/env python3
"""Builds "Nuvio TV DV": the official Nuvio TV webOS release plus an experimental
Dolby Vision hand-off to the webOS media pipeline, as a separate app
(space.nuvio.webosdv) so the official app stays installed.

Usage: build-nuvio-dv.py <extracted data dir of official ipk> <out dir>
Nuvio TV is GPL-3.0 (https://github.com/NuvioMedia/NuvioTVSmart); the source
change is in nuvio-dolby-vision.patch next to this script.
"""
import json, os, shutil, subprocess, sys

src, out = sys.argv[1], sys.argv[2]
OLD, NEW = 'space.nuvio.webos', 'space.nuvio.webosdv'
stage = os.path.join(out, 'stage')
shutil.rmtree(stage, ignore_errors=True)
os.makedirs(stage)

app_src = os.path.join(src, 'usr/palm/applications', OLD)
app_dst = os.path.join(stage, 'app')
shutil.copytree(app_src, app_dst)
services = []
for name in sorted(os.listdir(os.path.join(src, 'usr/palm/services'))):
    new_name = NEW + name[len(OLD):]
    shutil.copytree(os.path.join(src, 'usr/palm/services', name), os.path.join(stage, new_name))
    services.append(new_name)


def rename_ids(path):
    with open(path, encoding='utf-8') as f:
        s = f.read()
    s2 = s.replace(OLD + '.', NEW + '.').replace('"' + OLD + '"', '"' + NEW + '"')
    if s2 != s:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(s2)


for root, _, files in os.walk(stage):
    for fn in files:
        if fn.endswith(('.json', '.js', '.cjs', '.mjs', '.html')) and not fn.endswith('.min.js'):
            rename_ids(os.path.join(root, fn))

# ---- appinfo ----
ai_path = os.path.join(app_dst, 'appinfo.json')
ai = json.load(open(ai_path))
ai['id'] = NEW
ai['title'] = 'Nuvio TV DV'
ai['version'] = os.environ.get('DV_VERSION', ai['version'])
ai['services'] = [s for s in services if s.endswith('.service') and 'plugin' not in s] or ai.get('services', [])
json.dump(ai, open(ai_path, 'w'), indent=2)

# ---- Dolby Vision patch in the bundle ----
bundle_path = os.path.join(app_dst, 'app.bundle.js')
b = open(bundle_path, encoding='utf-8').read()


def patch(old, new):
    global b
    n = b.count(old)
    if n != 1:
        sys.exit(f'Patch-Stelle nicht eindeutig ({n}x): {old[:80]}')
    b = b.replace(old, new)


HELPERS = r'''(function(){
function tok(t,k){return new RegExp("(^|[^a-z0-9])"+k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"([^a-z0-9]|$)","i").test(t);}
window.__nuvioDvHint=function(c){
 if(!c||typeof c!=="object")return null;
 var p=c.streamPresentation||(c.raw&&c.raw.streamPresentation)||{};
 var bh=c.behaviorHints||{},rb=(c.raw&&c.raw.behaviorHints)||{};
 var t=[c.title,c.label,c.name,c.description,bh.filename,rb.filename,c.raw&&c.raw.filename,p.encode].concat(Array.isArray(p.visualTags)?p.visualTags:[]).filter(Boolean).join(" ").toLowerCase();
 var S=window.__nuvioDvState={text:t,reason:"",hint:null,sent:false,fallback:false};
 if(!t){S.reason="kein Stream-Name gefunden";return null;}
 var dv=t.indexOf("dolby vision")>=0||t.indexOf("dolbyvision")>=0||tok(t,"dv")||tok(t,"dovi");
 if(!dv){S.reason="kein DV im Namen";return null;}
 var hdr=tok(t,"hdr")||tok(t,"hdr10")||t.indexOf("hdr10+")>=0||tok(t,"p8");
 var p7=tok(t,"p7")||tok(t,"fel")||tok(t,"mel")||t.indexOf("profile 7")>=0;
 if(hdr){S.reason="DV mit HDR im Namen (Profil 8?) - nicht angefasst";return null;}
 if(p7){S.reason="Profil 7 im Namen - nicht angefasst";return null;}
 S.reason="DV Profil 5 erkannt";S.hint={profileId:5,trackType:"single"};
 return S.hint;
};
var box=null;
function esc(x){return String(x).replace(/[&<>]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function upd(){
 var S=window.__nuvioDvState,v=null,vs=document.querySelectorAll("video");
 for(var i=0;i<vs.length;i++){if(vs[i].currentSrc||vs[i].getAttribute("src")||vs[i].querySelector("source")){v=vs[i];break;}}
 if(!v||!S){if(box)box.style.display="none";return;}
 if(!box){box=document.createElement("div");box.style.cssText="position:fixed;top:16px;left:16px;z-index:2147483647;max-width:900px;padding:12px 16px;background:rgba(0,0,0,.8);color:#fff;font:20px/1.45 monospace;border:2px solid #f5c400;border-radius:8px;pointer-events:none;white-space:pre-wrap";document.body.appendChild(box);}
 var src=v.querySelector("source"),cur=String(v.currentSrc||v.getAttribute("src")||"");
 var way=src&&String(src.type).indexOf("mediaOption=")>=0?"direkt + DV-Angabe (mediaOption)":cur.indexOf("blob:")===0?"Zwischenplayer (MSE/HLS/DASH) - DV-Angabe nicht moeglich":"direkt, ohne DV-Angabe";
 box.style.display="block";
 box.innerHTML=esc("Nuvio DV Diagnose\n"+
  "Stream: "+S.text.slice(0,110)+"\n"+
  "Erkennung: "+S.reason+"\n"+
  "DV-Angabe gesendet: "+(S.sent?"JA":"nein")+"\n"+
  "Rueckfall auf normal: "+(S.fallback?"JA (TV hat abgelehnt)":"nein")+"\n"+
  "Abspielweg: "+way+"\n"+
  "Video: "+(v.videoWidth||"?")+"x"+(v.videoHeight||"?")+"  Zeit: "+(v.currentTime||0).toFixed(1)+"s");
}
setInterval(upd,1000);
window.__nuvioDvType=function(h){
 return"video/mp4;mediaOption="+encodeURIComponent(JSON.stringify({option:{externalStreamingInfo:{contents:{DolbyHdrInfo:{encryptionType:"clear",profileId:Number(h&&h.profileId)||5,trackType:h&&h.trackType==="dual"?"dual":"single"}}}}}));
};
})();
'''
b = HELPERS + b

# 1) player screen: attach the hint for the selected stream (l = stream candidate)
patch('p=h(h({},r&&"object"==typeof r?r:{}),Object.keys(c).length?{requestHeaders:c}:{});',
      'p=h(h(h({},r&&"object"==typeof r?r:{}),Object.keys(c).length?{requestHeaders:c}:{}),'
      '(function(){var x=window.__nuvioDvHint&&window.__nuvioDvHint(l||this.getCurrentStreamCandidate());'
      'return x?{dolbyVisionHint:x}:{}}).call(this));')

# 2) controller.play(): accept the hint
patch('preserveTrackSelections:w=!1}={}){',
      'preserveTrackSelections:w=!1,dolbyVisionHint:__dvh=null}={}){'
      'const __dvOpts=arguments[1]&&"object"==typeof arguments[1]?arguments[1]:{};')

# 3) native file path on webOS: send the Dolby Vision source when hinted
patch('r=t||i;if(r){if(this.applyWebOsStagedNativeSource(R,"native-file"),await this.prepareWebOsStagedNativePlayback(M,R),!this.isPlaybackRequestActive(M,C))return}else',
      'r=t||i,__dv=e.isWebOS()&&!!__dvh&&!this.isDolbyVisionSourceDisabled(C);'
      'if(__dv){if(this.applyWebOsDolbyVisionSource(R,__dvh),this.watchDolbyVisionSourceFailure(M,C,__dvOpts),'
      'await this.prepareWebOsStagedNativePlayback(M,R),!this.isPlaybackRequestActive(M,C))return}'
      'else if(r){if(this.applyWebOsStagedNativeSource(R,"native-file"),await this.prepareWebOsStagedNativePlayback(M,R),!this.isPlaybackRequestActive(M,C))return}else')
patch('beforePlay:r?null:()=>this.waitForNativeMediaId()',
      'beforePlay:r||__dv?null:()=>this.waitForNativeMediaId()')

# 4) controller helper methods
patch('applyWebOsStagedNativeSource(e,t="native-file"){',
      'applyWebOsDolbyVisionSource(u,h){if(!this.video)return!1;this.video.removeAttribute("src");'
      'Array.from(this.video.querySelectorAll("source")).forEach(n=>n.remove());'
      'var s=document.createElement("source");s.src=u;s.type=window.__nuvioDvType(h);this.video.appendChild(s);'
      'this.playbackEngine="native-file-dv";window.__nuvioDvState&&(window.__nuvioDvState.sent=!0);console.info("[Nuvio DV] Dolby Vision hint sent",h);return!0},'
      'isDolbyVisionSourceDisabled(u){return!!(this.dolbyVisionFailedUrls&&this.dolbyVisionFailedUrls.has(String(u||"")))},'
      'watchDolbyVisionSourceFailure(k,u,o){var v=this.video;if(!v)return;var s=v.querySelector("source"),done=!1,self=this;'
      'function clean(){done=!0;v.removeEventListener("error",fail,!0);s&&s.removeEventListener("error",fail);v.removeEventListener("playing",clean)}'
      'function fail(){if(done)return;clean();if(!self.isPlaybackRequestActive(k,u))return;'
      'self.dolbyVisionFailedUrls=self.dolbyVisionFailedUrls||new Set;self.dolbyVisionFailedUrls.add(String(u||""));window.__nuvioDvState&&(window.__nuvioDvState.fallback=!0);'
      'console.warn("[Nuvio DV] webOS rejected the Dolby Vision hint, retrying normal playback");'
      'self.play(u,Object.assign({},o,{dolbyVisionHint:null,preserveTrackSelections:!0}))}'
      'v.addEventListener("error",fail,!0);s&&s.addEventListener("error",fail);v.addEventListener("playing",clean)},'
      'applyWebOsStagedNativeSource(e,t="native-file"){')


# 5) Kodi hand-off: Dolby Vision profile 5 streams are played by Kodi, whose
#    webOS player applies Dolby Vision correctly. Kodi is controlled through its
#    JSON-RPC web interface (password protected) via Nuvio's background service.
KODI_APP = r"""(function(){
var SVC="luna://space.nuvio.webosdv.service/",KEY="nuvioDvKodi",bridges=[];
function luna(uri,params,cb){try{var br=new PalmServiceBridge();bridges.push(br);
 br.onservicecallback=function(m){var r;try{r=JSON.parse(m)}catch(x){r={returnValue:false,errorText:String(m)}}
  var i=bridges.indexOf(br);if(i>=0)bridges.splice(i,1);cb&&cb(r)};
 br.call(uri,JSON.stringify(params||{}));}catch(x){cb&&cb({returnValue:false,errorText:"Luna nicht verfuegbar: "+x.message})}}
function load(){try{return JSON.parse(localStorage.getItem(KEY)||"null")}catch(x){return null}}
function save(v){try{v?localStorage.setItem(KEY,JSON.stringify(v)):localStorage.removeItem(KEY)}catch(x){}}
function esc(x){return String(x==null?"":x).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var box=null,pendingCheck=false;
document.addEventListener("visibilitychange",function(){
 if(document.hidden||!pendingCheck)return;
 luna(SVC+"kodiStatus",{},function(r){
  if(r&&r.state==="error"){pendingCheck=false;show('<div style="font-size:36px;font-weight:bold;color:#ff8a8a">Kodi-Uebergabe fehlgeschlagen</div><div style="margin-top:12px">'+esc(r.errorText||"")+'</div><button id="nkX" style="'+BTN+'">OK</button>');var x=box.querySelector("#nkX");x.onclick=close;x.focus()}
  else if(r&&r.state==="ok"){pendingCheck=false;close()}});
});
function close(){if(box){box.remove();box=null}}
function show(html){close();box=document.createElement("div");
 box.style.cssText="position:fixed;inset:0;z-index:2147483646;background:rgba(10,10,12,.94);color:#fff;display:flex;align-items:center;justify-content:center;font:28px/1.5 sans-serif";
 box.innerHTML='<div style="max-width:1100px;padding:40px 56px;border:2px solid #7c3aed;border-radius:16px;background:#141418">'+html+'</div>';
 document.body.appendChild(box);return box}
var BTN="display:inline-block;margin:24px 20px 0 0;padding:16px 32px;border-radius:12px;border:3px solid transparent;background:#2a2a30;color:#fff;font:inherit;cursor:pointer";
var INP="display:block;width:640px;margin:8px 0 18px;padding:14px 18px;font:inherit;background:#222;color:#fff;border:3px solid #555;border-radius:10px";
function askCredentials(cb,note){
 var c=load()||{user:"kodi",pass:"",port:8080};
 var b=show('<div style="font-size:36px;font-weight:bold">Kodi-Zugang fuer Dolby Vision</div>'+
  '<div style="color:#bbb;margin:12px 0 24px">'+esc(note||"Dieser Stream ist Dolby Vision Profil 5. Er wird in Kodi abgespielt, damit die Farben stimmen. Gib einmalig die Zugangsdaten aus Kodi ein (Einstellungen > Dienste > Steuerung).")+'</div>'+
  'Benutzername<input id="nkU" style="'+INP+'" value="'+esc(c.user)+'">Passwort<input id="nkP" type="password" style="'+INP+'" value="'+esc(c.pass)+'">Port<input id="nkO" style="'+INP+'" value="'+esc(c.port)+'">'+
  '<button id="nkS" style="'+BTN+';background:#7c3aed">Speichern &amp; in Kodi abspielen</button><button id="nkH" style="'+BTN+'">Doch in Nuvio abspielen</button>');
 function ok(){var v={user:b.querySelector("#nkU").value.trim()||"kodi",pass:b.querySelector("#nkP").value,port:Number(b.querySelector("#nkO").value)||8080};save(v);cb(v)}
 b.querySelector("#nkS").onclick=ok;
 b.querySelector("#nkH").onclick=function(){cb(null)};
 b.querySelectorAll("input").forEach(function(i){i.addEventListener("keydown",function(ev){ev.stopPropagation();if(ev.keyCode===13){ev.preventDefault();ok()}},true)});
 b.querySelector(c.pass?"#nkS":"#nkP").focus();
}
window.__nuvioKodiHandoff=function(url,ctx,playHere){
 return new Promise(function(done){
  function here(){close();done(playHere())}
  function waiting(text){var b=show('<div style="font-size:36px;font-weight:bold">'+esc(text)+'</div><div style="color:#bbb;margin-top:12px">Dolby Vision Profil 5 wird in Kodi mit korrekten Farben abgespielt. Danach mit der App-Liste zurueck zu Nuvio wechseln.</div><button id="nkH" style="'+BTN+'">Doch in Nuvio abspielen</button>');b.querySelector("#nkH").onclick=here;b.querySelector("#nkH").focus()}
  function fail(text,auth){var b=show('<div style="font-size:36px;font-weight:bold;color:#ff8a8a">Kodi-Uebergabe fehlgeschlagen</div><div style="margin-top:12px">'+esc(text)+'</div><button id="nkR" style="'+BTN+';background:#7c3aed">'+(auth?"Zugangsdaten aendern":"Nochmal versuchen")+'</button><button id="nkH" style="'+BTN+'">In Nuvio abspielen</button>');
   b.querySelector("#nkR").onclick=function(){auth?askCredentials(function(c){c?go(c):here()},"Kodi hat die Zugangsdaten abgelehnt. Bitte pruefen."):go(load())};b.querySelector("#nkH").onclick=here;b.querySelector("#nkR").focus()}
  function go(c){
   waiting("Wird in Kodi geoeffnet ...");
   pendingCheck=true;
   // The service keeps running while Nuvio is suspended in the background,
   // so the job must be handed over before Kodi takes the foreground.
   luna(SVC+"kodiPlay",{url:url,headers:(ctx&&ctx.requestHeaders)||{},user:c.user,pass:c.pass,port:c.port},function(r){
    pendingCheck=false;
    if(r&&r.returnValue){waiting("Laeuft in Kodi");setTimeout(close,8000);done();return}
    fail((r&&r.errorText)||"Unbekannter Fehler",r&&r.errorCode==="KODI_AUTH")});
   setTimeout(function(){luna("luna://com.webos.applicationManager/launch",{id:"org.xbmc.kodi"})},400);
  }
  var c=load();
  if(c&&c.pass)go(c);else askCredentials(function(v){v?go(v):here()});
 });
};
})();
"""
b = KODI_APP + b
patch('Promise.resolve(e.play(o,p))',
      'Promise.resolve(p&&p.dolbyVisionHint&&window.__nuvioKodiHandoff?'
      'window.__nuvioKodiHandoff(o,p,function(){return e.play(o,Object.assign({},p,{dolbyVisionHint:null}))}):e.play(o,p))')

svc_path = os.path.join(stage, NEW + '.service', 'src', 'index.js')
svc = open(svc_path, encoding='utf-8').read()
SVC_ANCHOR = 'service.register("audioTranscodeStop",function(e){audioTranscode.stop((e.payload||{}).id),e.respond({returnValue:!0})});'
assert svc.count(SVC_ANCHOR) == 1, 'Dienst-Ankerstelle nicht eindeutig'
KODI_SVC = r"""service.register("kodiPlay",function(e){
var p=e.payload||{},http=require("http"),port=Number(p.port)||8080,deadline=Date.now()+60000;global.__nuvioKodiLast={state:"waiting",at:Date.now()};function reply(r){global.__nuvioKodiLast=Object.assign({state:r.returnValue?"ok":"error",at:Date.now()},r);e.respond(r)}function note(msg,cb){rpc({jsonrpc:"2.0",id:9,method:"GUI.ShowNotification",params:{title:"Nuvio DV",message:msg,displaytime:8000}},function(){cb&&cb()})}
var auth="Basic "+Buffer.from(String(p.user||"kodi")+":"+String(p.pass||"")).toString("base64");
var file=String(p.url||""),h=p.headers&&typeof p.headers==="object"?p.headers:{},hk=Object.keys(h).filter(function(k){return h[k]!=null&&String(h[k])!==""&&k.toLowerCase()!=="range"});
if(hk.length)file+="|"+hk.map(function(k){return k+"="+encodeURIComponent(String(h[k]))}).join("&");
function rpc(body,cb){var d=JSON.stringify(body),done=false;function fin(a,b,c){if(!done){done=true;cb(a,b,c)}}
 var req=http.request({host:"127.0.0.1",port:port,path:"/jsonrpc",method:"POST",headers:{"Content-Type":"application/json","Content-Length":Buffer.byteLength(d),"Authorization":auth}},function(res){var t="";res.on("data",function(x){t+=x});res.on("end",function(){fin(null,res.statusCode,t)})});
 req.setTimeout(4000,function(){req.abort();fin(new Error("timeout"))});req.on("error",function(err){fin(err)});req.end(d)}
function attempt(){rpc({jsonrpc:"2.0",id:1,method:"JSONRPC.Ping"},function(err,status){
 if(err){if(Date.now()<deadline)return setTimeout(attempt,1000);return reply({returnValue:false,errorCode:"KODI_UNREACHABLE",errorText:"Kodi antwortet nicht auf Port "+port+". Ist in Kodi unter Einstellungen > Dienste > Steuerung 'Steuerung ueber HTTP erlauben' eingeschaltet?"})}
 if(status===401)return reply({returnValue:false,errorCode:"KODI_AUTH",errorText:"Kodi hat Benutzername oder Passwort abgelehnt."});
 rpc({jsonrpc:"2.0",id:2,method:"Player.Open",params:{item:{file:file}}},function(err2,st2,txt){
  if(err2){var m1="Fehler beim Starten in Kodi: "+err2.message;return note(m1,function(){reply({returnValue:false,errorCode:"KODI_PLAY",errorText:m1})})}
  var r={};try{r=JSON.parse(txt)}catch(x){}
  if(r&&r.error){var m2="Kodi meldet: "+(r.error.message||JSON.stringify(r.error));return note(m2,function(){reply({returnValue:false,errorCode:"KODI_PLAY",errorText:m2})})}
  note("Dolby-Vision-Stream von Nuvio wird geladen ...");reply({returnValue:true})})})}
attempt()});service.register("kodiStatus",function(e){e.respond(Object.assign({returnValue:true},global.__nuvioKodiLast||{state:"none"}))});"""
svc = svc.replace(SVC_ANCHOR, SVC_ANCHOR + KODI_SVC)
open(svc_path, 'w', encoding='utf-8').write(svc)

sj_path = os.path.join(stage, NEW + '.service', 'services.json')
sj = json.load(open(sj_path))
cmds = sj['services'][0].setdefault('commands', [])
if not any(c.get('name') == 'kodiPlay' for c in cmds):
    cmds.append({'name': 'kodiPlay', 'description': 'Hand a Dolby Vision stream to Kodi via JSON-RPC', 'public': True})
if not any(c.get('name') == 'kodiStatus' for c in cmds):
    cmds.append({'name': 'kodiStatus', 'description': 'Result of the last Kodi hand-off', 'public': True})
json.dump(sj, open(sj_path, 'w'), indent=2)

open(bundle_path, 'w', encoding='utf-8').write(b)

with open(os.path.join(app_dst, 'NUVIO-DV-NOTICE.txt'), 'w') as f:
    f.write('Nuvio TV DV: modified build of Nuvio TV 1.3.6 (GPL-3.0, '
            'https://github.com/NuvioMedia/NuvioTVSmart) with an experimental Dolby Vision '
            'hand-off for the webOS media pipeline. Changes: see nuvio-dolby-vision.patch.\n')

subprocess.run(['ares-package', app_dst] + [os.path.join(stage, s) for s in services] + ['-o', out],
               check=True)
print('OK:', [f for f in os.listdir(out) if f.endswith('.ipk')])
