"""Build the shared Arabic voice pack for روضة الدروس with the open Piper voice ar_JO-kareem.

Every item the program can speak (letters with their vowels, numbers, shapes, praise, behaviour cards)
is synthesised, encoded as MP3 and stored in voices/*.json, which every screen imports by itself.
"""
import base64, json, os, subprocess, sys, tempfile, wave

items = json.load(open("tools/voice-items.json", encoding="utf-8"))
model = sys.argv[1]
out_name = sys.argv[2] if len(sys.argv) > 2 else "voices/piper-kareem.json"

from piper import PiperVoice  # noqa: E402

voice = PiperVoice.load(model)
syn_cfg = None
try:
    from piper import SynthesisConfig  # piper-tts >= 1.3
    syn_cfg = SynthesisConfig(length_scale=1.15, noise_scale=0.5, noise_w_scale=0.6)
except Exception:
    pass


def synth(text, path):
    with wave.open(path, "wb") as wf:
        if hasattr(voice, "synthesize_wav"):
            voice.synthesize_wav(text, wf, syn_config=syn_cfg) if syn_cfg else voice.synthesize_wav(text, wf)
        else:
            voice.synthesize(text, wf, length_scale=1.15)


pack = {"format": "rawda-voice-pack", "version": 1, "id": "piper-kareem", "voice": "كريم (صوت مفتوح المصدر)", "label": "ذكر · Piper، مدوّنة الكلام العربي", "items": {}}
ok = 0
with tempfile.TemporaryDirectory() as td:
    for i, (key, spoken) in enumerate(items):
        wav, mp3 = os.path.join(td, "a.wav"), os.path.join(td, "a.mp3")
        try:
            synth(spoken, wav)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav,
                            "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.12",
                            "-ac", "1", "-ar", "22050", "-b:a", "48k", mp3], check=True)
            pack["items"][key] = {"type": "audio/mpeg", "b64": base64.b64encode(open(mp3, "rb").read()).decode()}
            ok += 1
        except Exception as e:  # keep going; a missing clip falls back to the device voice
            print("failed:", key, e, file=sys.stderr)
        if i % 50 == 0:
            print(f"{i}/{len(items)}", flush=True)

os.makedirs(os.path.dirname(out_name), exist_ok=True)
json.dump(pack, open(out_name, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"done: {ok}/{len(items)} clips, {os.path.getsize(out_name)/1e6:.1f} MB")
if ok < len(items) * 0.9:
    sys.exit(1)
