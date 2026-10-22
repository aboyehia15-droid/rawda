"""Speech segments (start, end) of each Noorania lesson recording, from ffmpeg silencedetect."""
import json, os, re, subprocess, sys
src, out = sys.argv[1], sys.argv[2]
res = {}
for i in range(1, 18):
    f = os.path.join(src, f"n{i}.mp3")
    dur = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", subprocess.run(["ffmpeg", "-i", f], capture_output=True, text=True).stderr).groups()[2]) if False else None
    best = None
    for db, d in [(-30, 0.18), (-35, 0.25), (-28, 0.15)]:
        err = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", f"silencedetect=noise={db}dB:d={d}", "-f", "null", "-"], capture_output=True, text=True).stderr
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err); total = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
        se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
        segs, t = [], 0.0
        for a, b in zip(ss, se + [total]):
            if a - t > 0.08: segs.append([round(t, 2), round(a, 2)])
            t = b
        if total - t > 0.08: segs.append([round(t, 2), round(total, 2)])
        cand = {"db": db, "d": d, "dur": round(total, 2), "segs": segs}
        res.setdefault(str(i), {"alts": []})["alts"].append(cand)
    print(i, [(a["db"], len(a["segs"])) for a in res[str(i)]["alts"]])
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, "w"), separators=(",", ":"))
