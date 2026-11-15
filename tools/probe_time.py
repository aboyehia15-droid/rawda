import asyncio, json, http.server, threading, functools, sys
from playwright.async_api import async_playwright
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=".")
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8899), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
open("p.html", "w").write("<html><body>x</body></html>")
JS = """async ([rate, from]) => {
 const a = new Audio('n2.mp3'); a.crossOrigin='anonymous';
 await new Promise(r => a.addEventListener('loadedmetadata', r, {once:true}));
 const ac = new AudioContext(); const src = ac.createMediaElementSource(a); const an = ac.createAnalyser(); an.fftSize = 512; src.connect(an); an.connect(ac.destination);
 const buf = new Float32Array(512); const on = []; let loud = false, qt = 0;
 const K=376.32/a.duration; const off=from-from/K; a.currentTime = from/K; a.playbackRate = rate; await a.play();
 return await new Promise(res => {
   const iv = setInterval(() => { an.getFloatTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v));
     const db = 20*Math.log10(m+1e-9); if (db > -30) { if (!loud) on.push(+(a.currentTime+off).toFixed(2)); loud = true; qt = 0 } else if (++qt > 3) loud = false;
     if (a.ended || a.currentTime > from + 60*rate) { clearInterval(iv); res({dur: a.duration, end: a.currentTime, on}) } }, 5);
 });
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pg = await b.new_page(); await pg.goto("http://127.0.0.1:8899/p.html")
        out = {}
        for rate, frm in [(1, 300), (1, 150)]:
            out[f"{rate}@{frm}"] = await pg.evaluate(JS, [rate, frm])
            print(rate, frm, json.dumps(out[f"{rate}@{frm}"])[:2500], flush=True)
        await b.close()
asyncio.run(main())
