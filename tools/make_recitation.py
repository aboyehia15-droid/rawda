"""Minshawi, teaching recitation for children: one file per surah (1, 58-114) + start time of every verse -> q/t/"""
import json, os, subprocess, urllib.request, sys
AY={1:7,58:22,59:24,60:13,61:14,62:11,63:11,64:18,65:12,66:12,67:30,68:52,69:52,70:44,71:28,72:28,73:20,74:56,75:40,76:31,77:50,78:40,79:46,80:42,81:29,82:19,83:36,84:25,85:22,86:17,87:19,88:26,89:30,90:20,91:15,92:21,93:11,94:8,95:8,96:19,97:5,98:8,99:8,100:11,101:11,102:8,103:3,104:9,105:5,106:4,107:7,108:3,109:6,110:3,111:5,112:4,113:5,114:6}
CANDS=["https://everyayah.com/data/Minshawy_Teacher_128kbps/","https://everyayah.com/data/Minshawy_Murattal_Teacher_128kbps/","https://everyayah.com/data/Minshawi_Teacher_128kbps/"]
log=open("tools/recite-log.txt","w")
def get(u,p):
    for t in range(3):
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=urllib.request.urlopen(req,timeout=60).read()
            if len(d)>2000: open(p,"wb").write(d); return True
        except Exception as e: log.write(f"retry {u} {e}\n")
    return False
os.makedirs("/tmp/a",exist_ok=True)
base=None
for c in CANDS:
    ok=get(c+"078001.mp3","/tmp/a/probe.mp3");log.write(f"probe {c} {ok}\n");log.flush()
    if ok: base=c;break
if not base: log.write("no source\n");sys.exit(0)
dur=lambda p: float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip() or 0)
os.makedirs("q/t",exist_ok=True);idx={}
for s,n in AY.items():
    files=[]
    if s not in (1,9):
        if not get(base+"001001.mp3","/tmp/a/bas.mp3"): log.write(f"no basmala {s}\n");continue
        files.append("/tmp/a/bas.mp3")
    okall=True
    for a in range(1,n+1):
        p=f"/tmp/a/{s:03d}{a:03d}.mp3"
        if not get(f"{base}{s:03d}{a:03d}.mp3",p): okall=False;break
        files.append(p)
    if not okall: log.write(f"surah {s} incomplete\n");continue
    # normalise each piece, then join
    wavs=[]
    for i,f in enumerate(files):
        w=f"/tmp/a/w{i}.wav";subprocess.run(["ffmpeg","-loglevel","error","-y","-i",f,"-ac","1","-ar","22050",w],check=True);wavs.append(w)
    t=[];acc=0.0;ds=[dur(w) for w in wavs]
    b=ds[0] if s not in (1,9) else 0.0
    for i,d in enumerate(ds):
        if s not in (1,9) and i==0: acc+=d;continue
        t.append(round(acc,3));acc+=d
    open("/tmp/a/list.txt","w").write("".join(f"file '{w}'\n" for w in wavs))
    subprocess.run(["ffmpeg","-loglevel","error","-y","-f","concat","-safe","0","-i","/tmp/a/list.txt","-ac","1","-b:a","48k",f"q/t/{s:03d}.mp3"],check=True)
    idx[str(s)]={"b":round(b,3),"t":t,"d":round(acc,3)};log.write(f"surah {s} ok {acc:.0f}s\n");log.flush()
    for w in wavs: os.remove(w)
json.dump(idx,open("q/t/index.json","w"),separators=(",",":"))
log.write(f"done {len(idx)}\n")
