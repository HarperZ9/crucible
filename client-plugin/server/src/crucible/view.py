"""A registry viewer in one offline HTML file that re-hashes each claim in the browser.

``crucible view`` renders the registry (theses, claim bodies, stored hashes, and the seal and
body checks ``Registry`` ran while the page was built) into one HTML file with a bundled
JavaScript SHA-256. The page recomputes each claim body's hash in the browser and compares it
with the stored hash, so editing a character in a claim turns its chip to CORRUPT with no server
and no network. A self-test over two known SHA-256 vectors runs on load, and the page renders no
verdict until it passes.

What the page checks: each body against the hash embedded beside it. It does not recompute a
thesis seal in the browser, so someone who rewrites a body and its hash together in the HTML file
is not caught by the page alone; the seal status shown per thesis was computed from the registry
when the page was built, and ``crucible registry verify`` re-derives it from disk.

``build_view`` reads the registry and returns a JSON-able pack. The embedded body and hash pairs
are the ones the registry stored, so the in-browser check reproduces ``Registry.verify``.
"""
from __future__ import annotations

import json


def build_view(registry) -> dict:
    """Assemble the view pack from a registry: theses (with claim bodies + shas),
    assessment verdict history, and the integrity matrix (body + seal)."""
    theses = []
    for row in registry.theses():
        claims = []
        for cr in row.get("claims", []):
            sha = cr.get("sha256", "")
            try:
                body = registry.read_body(sha)
            except (OSError, ValueError):  # a missing body, or a row whose hash is not a sha256
                body = ""
            claims.append({"id": cr.get("id", ""), "sha256": sha if isinstance(sha, str) else "",
                           "body": body})
        theses.append({"id": row.get("id", ""), "title": row.get("title", ""),
                       "disposition": row.get("disposition", ""),
                       "seal": row.get("seal", ""), "claims": claims})
    assessments = []
    for a in registry.assessments():
        assessments.append({"thesis_id": a.get("thesis_id", ""),
                            "claims": a.get("claims", 0), "match": a.get("match", 0),
                            "drift": a.get("drift", 0), "unverifiable": a.get("unverifiable", 0),
                            "disposition": a.get("disposition", "")})
    integrity = registry.verify()
    seals = registry.verify_seals()
    for thesis, seal_row in zip(theses, seals):  # both walk theses.jsonl in order
        thesis["seal_status"] = seal_row["status"]
    return {"schema": "crucible.view/1", "theses": theses,
            "assessments": assessments, "integrity": integrity, "seals": seals,
            "counts": {"theses": len(theses), "claims": sum(len(t["claims"]) for t in theses),
                       "assessments": len(assessments)}}


# A compact SHA-256 so the page recomputes the hash crucible.claim.content_hash computes. The
# input is encoded as UTF-8, surrogate pairs included, to match Python's str.encode("utf-8").
_SHA256_JS = r"""
function sha256(ascii){
 function rotr(n,x){return (x>>>n)|(x<<(32-n));}
 var K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
 var H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
 var bytes=[]; for(var i=0;i<ascii.length;i++){var c=ascii.charCodeAt(i);
  if(c>=0xd800&&c<0xdc00&&i+1<ascii.length){var d=ascii.charCodeAt(i+1);
   if(d>=0xdc00&&d<0xe000){c=0x10000+((c-0xd800)<<10)+(d-0xdc00);i++;
    bytes.push(240|(c>>18),128|((c>>12)&63),128|((c>>6)&63),128|(c&63));continue;}}
  if(c<128)bytes.push(c);
  else if(c<2048){bytes.push(192|(c>>6),128|(c&63));}
  else{bytes.push(224|(c>>12),128|((c>>6)&63),128|(c&63));}}
 var l=bytes.length*8; bytes.push(0x80); while((bytes.length%64)!=56)bytes.push(0);
 for(var i=7;i>=0;i--)bytes.push((l/Math.pow(2,i*8))&0xff);
 var w=new Array(64);
 for(var j=0;j<bytes.length;j+=64){
  for(var i=0;i<16;i++)w[i]=(bytes[j+i*4]<<24)|(bytes[j+i*4+1]<<16)|(bytes[j+i*4+2]<<8)|bytes[j+i*4+3];
  for(var i=16;i<64;i++){var s0=rotr(7,w[i-15])^rotr(18,w[i-15])^(w[i-15]>>>3);
   var s1=rotr(17,w[i-2])^rotr(19,w[i-2])^(w[i-2]>>>10);
   w[i]=(w[i-16]+s0+w[i-7]+s1)|0;}
  var a=H[0],b=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g=H[6],h=H[7];
  for(var i=0;i<64;i++){var S1=rotr(6,e)^rotr(11,e)^rotr(25,e);var ch=(e&f)^((~e)&g);
   var t1=(h+S1+ch+K[i]+w[i])|0;var S0=rotr(2,a)^rotr(13,a)^rotr(22,a);var maj=(a&b)^(a&c)^(b&c);
   var t2=(S0+maj)|0;h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;}
  H[0]=(H[0]+a)|0;H[1]=(H[1]+b)|0;H[2]=(H[2]+c)|0;H[3]=(H[3]+d)|0;
  H[4]=(H[4]+e)|0;H[5]=(H[5]+f)|0;H[6]=(H[6]+g)|0;H[7]=(H[7]+h)|0;}
 var out=''; for(var i=0;i<8;i++)out+=('00000000'+(H[i]>>>0).toString(16)).slice(-8); return out;
}
"""

# crucible.claim.content_hash hashes the claim_body JSON directly; the view's JS
# is handed the exact body string, so sha256(body) == the stored sha.
_CSS = """
:root{--bg:#f4f3ef;--ink:#0b0c0e;--muted:#565a62;--hair:rgba(11,12,14,.14);
--iris:#4636e8;--ok:#1f6b45;--bad:#b23b3b;--mono:ui-monospace,Consolas,monospace;--body:Arial,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);padding:1.4rem}
h1{font:600 1.2rem var(--body);margin:0 0 .2rem}
.sub{color:var(--muted);font-size:.85rem;max-width:70ch}
.selftest{display:inline-block;font:600 .72rem var(--mono);padding:.2em .6em;border-radius:6px;margin:.6rem 0;border:1px solid}
.selftest.ok{color:var(--ok);border-color:var(--ok)} .selftest.bad{color:var(--bad);border-color:var(--bad)}
.t{border:1px solid var(--hair);border-radius:10px;padding:.8rem 1rem;margin:.8rem 0;background:#fbfaf7}
.t h2{font:600 1rem var(--body);margin:.1rem 0 .1rem}
.t .meta{font:.72rem var(--mono);color:var(--muted)}
.claim{border-top:1px solid var(--hair);padding:.55rem 0;display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:start}
.claim .txt{font-size:.9rem}.claim .txt textarea{width:100%;font:.8rem var(--mono);border:1px solid var(--hair);border-radius:6px;padding:.35rem;min-height:2.6em;background:#fff;color:var(--ink)}
.claim .fals{color:var(--muted);font-size:.78rem;margin-top:.2rem}
.chip{font:600 .68rem var(--mono);padding:.2em .55em;border-radius:999px;border:1px solid;white-space:nowrap}
.chip.MATCH{color:var(--ok);border-color:var(--ok)} .chip.CORRUPT,.chip.SEAL_BROKEN{color:var(--bad);border-color:var(--bad)}
.sha{font:.66rem var(--mono);color:var(--muted);word-break:break-all}
.hint{font:.74rem var(--mono);color:var(--iris);margin-top:.3rem}
"""


_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>crucible registry: __NT__ theses</title>
<style>__CSS__</style></head><body>
<h1>crucible registry viewer</h1>
<div class="sub">__NT__ theses &middot; __NC__ claims &middot;
__NA__ witnessed assessments. Every claim's hash is recomputed in
your browser. <b>Edit any claim below and its chip turns CORRUPT.</b> Each seal status was
checked against the registry when this page was built.</div>
<div class="selftest" id="selftest">verifier self-test&hellip;</div>
<div id="theses"></div>
<script>__SHA__
const PACK=__DATA__;
// The stored sha is sha256 of the claim body (crucible.claim.claim_body). The page holds
// the exact body, so it recomputes sha256(body) and compares.
function verifierSelfTest(){
 const ok = sha256("")==="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
   && sha256("abc")==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
 const el=document.getElementById('selftest');
 el.textContent = ok ? 'verifier self-test: OK (SHA-256 known-vector)' : 'verifier self-test: FAILED';
 el.className='selftest '+(ok?'ok':'bad'); return ok;
}
function chip(status){return '<span class="chip '+esc(status)+'">'+esc(status)+'</span>';}
function render(){
 const root=document.getElementById('theses');root.innerHTML='';
 PACK.theses.forEach((t,ti)=>{
  const d=document.createElement('div');d.className='t';
  let h='<h2>'+esc(t.title)+'</h2><div class="meta">'+esc(t.id)+' · '+esc(t.disposition)+' · seal '+esc(t.seal.slice(0,16))+'… '+chip(t.seal_status||'SEAL_BROKEN')+'</div>';
  t.claims.forEach((c,ci)=>{
   h+='<div class="claim" data-t="'+ti+'" data-c="'+ci+'">'+
     '<div class="txt"><textarea>'+esc(c.body)+'</textarea>'+
     '<div class="sha">stored sha256: '+esc(c.sha256)+'</div>'+
     '<div class="hint" style="display:none">this body no longer matches its stored hash</div></div>'+
     '<div class="v"></div></div>';
  });
  d.innerHTML=h;root.appendChild(d);
 });
 document.querySelectorAll('.claim').forEach(el=>{
  const ta=el.querySelector('textarea');
  const recheck=()=>{
   const c=PACK.theses[+el.dataset.t].claims[+el.dataset.c];
   const live=sha256(ta.value);const ok=live===c.sha256;
   el.querySelector('.v').innerHTML=chip(ok?'MATCH':'CORRUPT');
   el.querySelector('.hint').style.display = ok?'none':'block';
  };
  ta.addEventListener('input',recheck);recheck();
 });
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
if(verifierSelfTest())render();
</script></body></html>"""


def render_view_html(pack: dict) -> str:
    data = json.dumps(pack, separators=(",", ":")).replace("<", "\\u003c")
    c = pack["counts"]
    return (_TEMPLATE
            .replace("__CSS__", _CSS)
            .replace("__SHA__", _SHA256_JS)
            .replace("__NT__", str(c["theses"]))
            .replace("__NC__", str(c["claims"]))
            .replace("__NA__", str(c["assessments"]))
            .replace("__DATA__", data))  # data last, so a claim body cannot be read as a token
