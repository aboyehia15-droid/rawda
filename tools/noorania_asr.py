"""Arabic transcript of one Noorania recording with word timestamps (faster-whisper)."""
import json, sys
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4)
segs, info = model.transcribe(src, language="ar", word_timestamps=True, vad_filter=True,
                              vad_parameters={"min_silence_duration_ms": 300}, beam_size=5,
                              condition_on_previous_text=False,
                              initial_prompt="القاعدة النورانية. الدرس. بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ. أَلِف بَا تَا ثَا جِيم حَا خَا")
res = []
for s in segs:
    res.append({"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text.strip(),
                "w": [[round(w.start, 2), round(w.end, 2), w.word.strip()] for w in (s.words or [])]})
    print(f"{s.start:7.2f} {s.end:7.2f} {s.text.strip()}", flush=True)
json.dump({"dur": info.duration, "segs": res}, open(out, "w"), ensure_ascii=False)
