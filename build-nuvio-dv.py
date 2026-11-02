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
 if(!t)return null;
 var dv=t.indexOf("dolby vision")>=0||t.indexOf("dolbyvision")>=0||tok(t,"dv")||tok(t,"dovi");
 if(!dv)return null;
 var hdr=tok(t,"hdr")||tok(t,"hdr10")||t.indexOf("hdr10+")>=0||tok(t,"p8");
 var p7=tok(t,"p7")||tok(t,"fel")||tok(t,"mel")||t.indexOf("profile 7")>=0;
 if(hdr||p7)return null;
 return{profileId:5,trackType:"single"};
};
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
      'this.playbackEngine="native-file-dv";console.info("[Nuvio DV] Dolby Vision hint sent",h);return!0},'
      'isDolbyVisionSourceDisabled(u){return!!(this.dolbyVisionFailedUrls&&this.dolbyVisionFailedUrls.has(String(u||"")))},'
      'watchDolbyVisionSourceFailure(k,u,o){var v=this.video;if(!v)return;var s=v.querySelector("source"),done=!1,self=this;'
      'function clean(){done=!0;v.removeEventListener("error",fail,!0);s&&s.removeEventListener("error",fail);v.removeEventListener("playing",clean)}'
      'function fail(){if(done)return;clean();if(!self.isPlaybackRequestActive(k,u))return;'
      'self.dolbyVisionFailedUrls=self.dolbyVisionFailedUrls||new Set;self.dolbyVisionFailedUrls.add(String(u||""));'
      'console.warn("[Nuvio DV] webOS rejected the Dolby Vision hint, retrying normal playback");'
      'self.play(u,Object.assign({},o,{dolbyVisionHint:null,preserveTrackSelections:!0}))}'
      'v.addEventListener("error",fail,!0);s&&s.addEventListener("error",fail);v.addEventListener("playing",clean)},'
      'applyWebOsStagedNativeSource(e,t="native-file"){')

open(bundle_path, 'w', encoding='utf-8').write(b)

with open(os.path.join(app_dst, 'NUVIO-DV-NOTICE.txt'), 'w') as f:
    f.write('Nuvio TV DV: modified build of Nuvio TV 1.3.6 (GPL-3.0, '
            'https://github.com/NuvioMedia/NuvioTVSmart) with an experimental Dolby Vision '
            'hand-off for the webOS media pipeline. Changes: see nuvio-dolby-vision.patch.\n')

subprocess.run(['ares-package', app_dst] + [os.path.join(stage, s) for s in services] + ['-o', out],
               check=True)
print('OK:', [f for f in os.listdir(out) if f.endswith('.ipk')])
