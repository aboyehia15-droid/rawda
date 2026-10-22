"""Align Noorania speech segments to the cells of each lesson -> noorania/map.json
units: cells in reading order (rows top->bottom, cells right->left), split into lessons at the lesson headings.
DP: every unit takes one or more consecutive speech segments; a few segments may be skipped at the start
(lesson title / introduction) and at the end; cost = squared deviation from the expected duration."""
import json, sys, math
cells = json.load(open(sys.argv[1])); sync = json.load(open(sys.argv[2])); out = sys.argv[3]
# headings the detector missed: page -> (row index, how the row splits into heading + text)
def split_rows(pg, rows):
    rows = [list(r) for r in rows]
    if pg == 24 and len(rows) > 6 and rows[6][0][0] != 'H':
        x, y, w, h = rows[6][0]; rows[6:7] = [[['H', x, y, w, h / 2]], [[x, y + h / 2, w, h / 2]]]
    if pg == 26 and len(rows) > 8 and rows[8][0][0] != 'H':
        x, y, w, h = rows[8][0]; cut = x + w * .5
        rows[8] = [['H', cut, y, x + w - cut, h], [x, y, cut - x, h]]
    return rows
LAST_ROWS = {29: 4}
units = [[] for _ in range(17)]; cur = 0; first = True
for pg in range(7, 30):
    rows = split_rows(pg, cells.get(str(pg), []))
    if pg in LAST_ROWS: rows = rows[:LAST_ROWS[pg]]
    for row in rows:
        for c in row:
            if c[0] == 'H':
                hu = {"pg": pg, "box": c[1:5], "wt": 3.0, "head": 1}
                if first: first = False; units[0].append(hu)
                else: cur += 1; units[min(cur, 16)].append(hu)
                continue
            x, y, w, h = c
            wt = 1.0 if w < .2 else max(1.0, w / .085)
            u = {"pg": pg, "box": [x, y, w, h], "wt": wt}
            if pg == 7 and not units[0]: u["e"] = 1.0; u["wt"] = 1.0   # the basmala: one utterance
            units[min(cur, 16)].append(u)
print("lessons starting with their heading:", sum(1 for u in units if u and u[0].get("head")))
print("headings ->", cur + 1, "lessons; units:", [len(u) for u in units])

def prep(segs):
    """pieces split by a very short pause are one utterance (the children's repeat pause is longer)"""
    mg = []
    for a, b in [x for x in segs if x[1] - x[0] >= .22]:
        if mg and a - mg[-1][1] < .8: mg[-1][1] = b
        else: mg.append([a, b])
    return mg

import re, os
STRIP = re.compile(r"[\u064b-\u065f\u0670\u0640.,،؛:!?]")
HAR = ("فت", "كسر", "ضم", "سكون", "تنو", "شد")
LNAMES = ("الف", "ألف", "همز", "با", "تا", "ثا", "جيم", "حا", "خا", "دال", "ذال", "را", "زا", "سين", "شين", "صاد", "ضاد", "طا", "ظا", "عين", "غين", "فا", "قاف", "كاف", "لام", "ميم", "نون", "ها", "واو", "يا")
def norm(w): return STRIP.sub("", w).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
def flags(segs, words):
    """text of each utterance from the transcript; st=1 when it introduces a box (letter name, then a vowel mark)"""
    out = []
    for a, b in segs:
        ws = [norm(w[2]) for w in words if a - .35 <= (w[0] + w[1]) / 2 <= b + .35]
        st = 0 if ws else None; seen_letter = False
        bare = {"فتحه", "فتحة", "كسره", "كسرة", "ضمه", "ضمة", "فتحتين", "كسرتين", "ضمتين", "سكون", "التنوين", "تنوين", "شده", "شدة", "الحركات"}
        for w in ws:
            if any(w.startswith(norm(n)) for n in LNAMES) and len(w) <= 5: seen_letter = True
            if any(h in w for h in HAR + ("بما", "بمر")) and (w not in bare or seen_letter or len(ws) > 1): st = 1; break
        if any(t in w for w in ws for t in ("الدرس", "تدريب", "الحروف", "حروف", "السكون", "الشده", "الشدة", "الشدتين", "اللين", "المد")): st = 0
        out.append((st, " ".join(ws)))
    return out

def align(U, segs, F=None, hcount=None):
    """each unit takes g consecutive utterances (g>=1), or several units share one utterance.
    cost: number of utterances near the expected count, the group ending on its longest
    utterance (the whole word after spelling), and duration near the expected share."""
    K, N = len(U), len(segs)
    if K == 0 or N == 0: return None
    W = [u["wt"] for u in U]; HEAD = [u.get("head", 0) for u in U]
    best = None
    for skip0 in range(0, 1):
        S = segs[skip0:]; n = len(S)
        D = [b - a for a, b in S]
        nh = sum(HEAD); bw = sum(w for w, h in zip(W, HEAD) if not h) or 1
        r = max(.3, (n - 2 * nh) / bw)            # utterances per unit of box weight
        E = [u.get("e") or (2.0 if h else max(.5, r * w)) for u, w, h in zip(U, W, HEAD)]
        c = sum(D) / max(1, sum(E))                # seconds per expected utterance
        G = max(8, math.ceil(3 * max(E)) + 2)
        INF = 1e18
        dp = [[INF] * (n + 1) for _ in range(K + 1)]; bk = [[0] * (n + 1) for _ in range(K + 1)]
        dp[0][0] = 0
        for i in range(1, K + 1):
            e = E[i - 1]
            for j in range(1, n + 1):
                bestv, bestg = INF, 0
                d = 0.0; mx = 0.0
                for g in range(1, G + 1):
                    if j - g < 0: break
                    dd = D[j - g]; d += dd; mx = max(mx, dd)
                    pv = dp[i - 1][j - g]
                    if pv >= INF: continue
                    if HEAD[i - 1] and i == 1 and hcount and g != hcount: continue
                    v = pv + (8 if HEAD[i - 1] else (.2 if F else 1)) * ((g - e) / max(e, 1)) ** 2 + (.1 if F else .3) * ((d - c * e) / max(c * e, .3)) ** 2
                    if F and not HEAD[i - 1]:
                        f0 = F[skip0 + j - g]
                        v += 2.5 if f0 == 0 else (.3 if f0 is None else 0)
                        v += 3.0 * sum(1 for q in range(j - g + 1, j) if F[skip0 + q] == 1)
                    if g > 1 and not HEAD[i - 1] and D[j - 1] < mx - 1e-6: v += .35
                    if v < bestv: bestv, bestg = v, g
                if j >= 1 and i >= 2:
                    for m in range(2, 4):
                        if i - m < 0: break
                        if any(HEAD[i - m:i]): break
                        pv = dp[i - m][j - 1]
                        if pv >= INF: continue
                        es = sum(E[i - m:i])
                        v = pv + ((1 - es) / max(es, 1)) ** 2 * m + ((4.0 if F[skip0 + j - 1] == 1 or (skip0 + j < len(F) and F[skip0 + j] == 1) or (skip0 + j - 2 >= 0 and F[skip0 + j - 2] == 1) else .7) if F else 1.2) * (m - 1)
                        if v < bestv: bestv, bestg = v, -m
                dp[i][j] = bestv; bk[i][j] = bestg
        for j in range(1, n + 1):
            v = dp[K][j] + 2.0 * (n - j) + .8 * skip0
            if best is None or v < best[0]: best = (v, skip0, j, bk, S, W)
    if best is None or best[0] >= 1e17: return None
    v, skip0, j, bk, S, W = best
    res = []; i = K
    while i > 0:
        g = bk[i][j]
        if g < 0:
            m = -g; a, b = S[j - 1]; ws = W[i - m:i]; tw = sum(ws); t = b
            for w in reversed(ws):
                dd = (b - a) * w / tw; res.append((t - dd, t)); t -= dd
            j -= 1; i -= m
        else:
            res.append((S[j - g][0], S[j - 1][1])); j -= g; i -= 1
    res.reverse()
    return res, v / K, skip0

M = {}
for k in range(17):
    alts = sync.get(str(k + 1), {}).get("alts", [])
    if not alts or not units[k]: print(k + 1, "no data"); continue
    asr = os.path.join(os.path.dirname(out), "asr", f"asr-{k+1}.json")
    words = [w for sg in json.load(open(asr))["segs"] for w in sg["w"]] if os.path.exists(asr) else []
    scored = []
    for a in alts:
        sg = prep(a["segs"]); F = None; hc = None
        if words:
            fl = flags(sg, words); st = [f[0] for f in fl]
            first = next((i for i, f in enumerate(st) if f == 1), None)
            print(f'   lesson {k+1} db {a["db"]}: {st.count(1)} box starts heard of {len(st)} utterances')
            small = sorted(u['wt'] for u in units[k])[len(units[k]) // 2] <= 1.5
            if small and st.count(1) >= max(3, .15 * len(units[k])):
                F = st
                if first is not None and sg[first][0] < 90: hc = max(1, first)
        r = align(units[k], sg, F, hc) or align(units[k], sg)
        if r: scored.append((r[1], a, r))
    # prefer the -35 dB reading (fewest false splits) unless another fits clearly better
    scored.sort(key=lambda x: x[0]); pref = [x for x in scored if x[1]["db"] == -35]
    pick = scored[0] if not pref or scored[0][0] < .7 * pref[0][0] else pref[0]
    sc, a, (tm, _, skip0) = pick
    M[str(k + 1)] = [[round(t0, 2), round(t1, 2), u["pg"]] + u["box"] for (t0, t1), u in zip(tm, units[k])]
    print(f"   header {tm[0][0]:.1f}-{tm[0][1]:.1f}s; flags {'yes' if words else 'no'}")
    print(f"lesson {k+1}: units {len(units[k])} segs {len(a['segs'])} (db {a['db']}) cost {sc:.2f} intro-skip {skip0} first {tm[0][0]:.1f}s dur {a['dur']}")
json.dump(M, open(out, "w"), separators=(",", ":"))
