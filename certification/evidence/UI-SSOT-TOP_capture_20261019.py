import json,datetime,pathlib
from playwright.sync_api import sync_playwright
OUT=pathlib.Path("capture")
T=[("S8023_ROOT","http://127.0.0.1:8023/"),("S8023_LIVECOPY","http://127.0.0.1:8023/live-copy"),("S8031_ROOT","http://127.0.0.1:8031/"),("S8031_LIVECOPY","http://127.0.0.1:8031/live-copy")]
res=[]
pw=sync_playwright().start()
br=pw.chromium.launch(headless=True)
for n,u in T:
    ctx=br.new_context();pg=ctx.new_page();rec={"target":n,"requested_url":u}
    try:
        r=pg.goto(u,wait_until="load",timeout=20000);pg.wait_for_timeout(2500)
        rec["http_status"]=r.status if r else None;rec["final_url"]=pg.url;rec["title"]=pg.title()
        rec["captured_at_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
        d=pg.content();f=OUT/(n+".html");f.write_text(d,encoding="utf-8")
        rec["dom_file"]=str(f.resolve());rec["dom_bytes"]=len(d);rec["has_top_bar"]=("Normalisation Base" in d)
        t=pg.query_selector("div.top")
        if t:
            rec["top_bar_text"]=t.inner_text();rec["top_bar_html"]=t.inner_html()
            rec["top_inputs"]=pg.eval_on_selector_all("div.top input","e=>e.map(x=>({name:x.name,value:x.value}))")
            rec["top_selects"]=pg.eval_on_selector_all("div.top select","e=>e.map(x=>({name:x.name,value:x.value,text:x.options[x.selectedIndex]?x.options[x.selectedIndex].text:null}))")
            rec["top_spans"]=pg.eval_on_selector_all("div.top span","e=>e.map(x=>({cls:x.className,text:x.innerText.trim()}))")
            rec["top_buttons"]=pg.eval_on_selector_all("div.top button","e=>e.map(x=>x.innerText.trim())")
    except Exception as ex:
        rec["error"]=type(ex).__name__+": "+str(ex)[:300]
    ctx.close();res.append(rec)
br.close();pw.stop()
OUT.joinpath("capture_summary.json").write_text(json.dumps(res,indent=1),encoding="utf-8")
[print(r["target"],r.get("http_status"),r.get("title"),r.get("has_top_bar"),r.get("error")) for r in res]
