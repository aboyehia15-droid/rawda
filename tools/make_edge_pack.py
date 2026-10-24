"""Arabic voice packs for روضة الدروس from Microsoft's natural (neural) Arabic voices, via edge-tts (free, no key).
Each pack holds every short item the program speaks and is imported by every screen from voices/*.json."""
import asyncio, base64, json, os, subprocess, sys, tempfile
import edge_tts

items = json.load(open("tools/voice-items.json", encoding="utf-8"))
# everything the reading journey says (stage words, letter positions, game questions): in the main voice too
read_items = json.load(open("tools/voice-items-read.json", encoding="utf-8")) if os.path.exists("tools/voice-items-read.json") else []
VOICES = [
    ("ar-SA-HamedNeural", "edge-hamed", "حامد (صوت طبيعي)", "ذكر · سعودي · Microsoft", True),
    ("ar-SA-ZariyahNeural", "edge-zariyah", "زارية (صوت طبيعي)", "أنثى · سعودية · Microsoft", False),
]

async def one(voice, text, path):
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate="-12%").save(path)
            if os.path.getsize(path) > 500: return True
        except Exception as e:
            print("retry", text, e, file=sys.stderr)
        await asyncio.sleep(2 + attempt * 3)
    return False

async def main():
    only = sys.argv[1:]
    for voice, pid, name, label, full in VOICES:
        if only and pid not in only: continue
        todo = items + (read_items if full else [])
        out = f"voices/{pid}.json"
        pack = {"format": "rawda-voice-pack", "version": 1, "id": pid, "voice": name, "label": label, "items": {}}
        ok = 0
        with tempfile.TemporaryDirectory() as td:
            raw, mp3 = os.path.join(td, "a.mp3"), os.path.join(td, "b.mp3")
            for i, (key, spoken) in enumerate(todo):
                if not await one(voice, spoken, raw): print("failed:", key, file=sys.stderr); continue
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw,
                                "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.12",
                                "-ac", "1", "-ar", "24000", "-b:a", "48k", mp3], check=True)
                pack["items"][key] = {"type": "audio/mpeg", "b64": base64.b64encode(open(mp3, "rb").read()).decode()}
                ok += 1
                if i % 50 == 0: print(pid, f"{i}/{len(todo)}", flush=True)
        if ok >= len(todo) * 0.9:
            json.dump(pack, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            print(f"{pid}: {ok}/{len(todo)} clips, {os.path.getsize(out)/1e6:.1f} MB")
        else:
            print(f"{pid}: only {ok}/{len(todo)} clips, not saved", file=sys.stderr)

asyncio.run(main())
