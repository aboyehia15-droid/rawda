"""Build the shared Arabic voice pack with Google Gemini text-to-speech (key from the GEMINI_API_KEY secret)."""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error

key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key:
    print("GEMINI_API_KEY secret is missing; nothing to do."); sys.exit(0)
cfg = dict(l.split("=", 1) for l in open("tools/gemini-voice.txt", encoding="utf-8").read().split() if "=" in l)
VOICES = [v for v in cfg.get("voices", cfg.get("voice", "Kore")).split(",") if v]
LABELS = {"Kore": "أنثى · حازم وواضح", "Charon": "ذكر · رصين هادئ", "Puck": "ذكر · مرح", "Aoede": "أنثى · منساب لطيف", "Leda": "أنثى · شبابي", "Orus": "ذكر · حازم", "Zephyr": "أنثى · مشرق", "Fenrir": "ذكر · متحمس", "Achird": "ذكر · ودود", "Sulafat": "أنثى · دافئ"}
voice = VOICES[0]
models = [m for m in cfg.get("models", "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-2.5-flash-preview-tts").split(",") if m]
items = json.load(open("tools/voice-items.json", encoding="utf-8"))
prev = {}
if os.path.exists("voices/.gemini-done.json"):
    prev = json.load(open("voices/.gemini-done.json", encoding="utf-8"))


def call(model, text):
    body = {"contents": [{"role": "user", "parts": [{"text": f"اقرأ النص التالي فقط بالعربية الفصحى، بصوت معلم روضة واضح ودافئ وبطيء قليلًا، وانطق التشكيل كما هو: {text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    for p in d["candidates"][0]["content"]["parts"]:
        inl = p.get("inlineData") or p.get("inline_data")
        if inl:
            return base64.b64decode(inl["data"]), inl.get("mimeType") or inl.get("mime_type") or ""
    raise RuntimeError("no audio")


model = None
for m in models:
    try:
        call(m, "بِسْمِ اللَّه"); model = m; break
    except urllib.error.HTTPError as e:
        print("model", m, "->", e.code, e.read()[:300])
if not model:
    print("No Gemini TTS model is usable with this key."); sys.exit(1)
print("using", model, "voice", voice)

for voice in VOICES:
    out = f"voices/gemini-{voice}.json"
    old = "voices/الحزمة-الصوتية-العربية.json"
    if not os.path.exists(out) and voice == "Kore" and os.path.exists(old) and prev.get("Kore"):
        o = json.load(open(old, encoding="utf-8"))
        json.dump({"format": "rawda-voice-pack", "version": 1, "items": {k: o["items"][k] for k in prev["Kore"] if k in o["items"]}}, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    if os.path.exists(old) and os.path.exists("voices/piper-kareem.json"):
        os.remove(old)  # the old mixed pack is replaced by one file per voice
    pack = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {"format": "rawda-voice-pack", "version": 1, "items": {}}
    pack["voice"] = f"Gemini — {voice}"
    pack["id"] = f"gemini-{voice}"
    pack["label"] = LABELS.get(voice, "")
    done = set(prev.get(voice, []))
    ok = 0
    quota_hit = False
    with tempfile.TemporaryDirectory() as td:
        for i, (k, spoken) in enumerate(items):
            if k in done:
                continue
            if quota_hit:
                break
            for attempt in range(6):
                try:
                    raw, mt = call(model, spoken)
                    src = os.path.join(td, "a.raw")
                    open(src, "wb").write(raw)
                    inp = ["-i", src] if (raw[:4] == b"RIFF" or "wav" in mt) else ["-f", "s16le", "-ar", (mt.split("rate=")[-1] if "rate=" in mt else "24000"), "-ac", "1", "-i", src]
                    mp3 = os.path.join(td, "a.mp3")
                    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inp, "-af",
                                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.12",
                                    "-ac", "1", "-ar", "24000", "-b:a", "48k", mp3], check=True)
                    pack["items"][k] = {"type": "audio/mpeg", "b64": base64.b64encode(open(mp3, "rb").read()).decode()}
                    done.add(k); ok += 1
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        if attempt == 5:
                            quota_hit = True
                            break
                        time.sleep(min(90, 15 * (attempt + 1))); continue
                    print("fail", k, e.code); break
                except Exception as e:
                    print("fail", k, e); break
            if i % 25 == 0:
                print(f"{i}/{len(items)}", flush=True)
            time.sleep(0.5)

    json.dump(pack, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    prev[voice] = sorted(done)
    json.dump(prev, open("voices/.gemini-done.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"gemini clips this run: {ok}; total with {voice}: {len(done)}/{len(items)}")
    if len(done) < len(items) or quota_hit:
        break  # quota reached: continue this voice next run before starting another
