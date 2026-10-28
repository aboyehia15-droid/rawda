"""Align Noorania speech segments to the cells of each lesson -> noorania/map.json
units: cells in reading order (rows top->bottom, cells right->left), split into lessons at the lesson headings.
DP: every unit takes one or more consecutive speech segments; a few segments may be skipped at the start
(lesson title / introduction) and at the end; cost = squared deviation from the expected duration."""
import json, sys, math
cells = json.load(open(sys.argv[1])); sync = json.load(open(sys.argv[2])); out = sys.argv[3]
# headings the detector missed: page -> (row index, how the row splits into heading + text)
def split_rows(pg, rows):
    return [list(r) for r in rows]
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

def families(segs, words, fl):
    """how many letter families (3 boxes each) an utterance reads at once, in quick-review passages"""
    fam = []
    for i, (st, t) in enumerate(fl):
        q = 0
        recent = any(fl[j][0] == 1 for j in range(max(0, i - 2), i))
        if st == 0 and not recent and t:
            q = sum(1 for w in t.split() if len(w) >= 4 and not any(h in w for h in HAR) and not any(w.startswith(norm(n)) and len(w) <= 5 for n in LNAMES))
        fam.append(q)
    return fam

def align(U, segs, F=None, hcount=None, FAM=None, wordy=False, TXT=None):
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
                        if wordy:
                            # a word box: spelled letters ... then the whole word; never split between spelled letters
                            jb = skip0 + j - g
                            if jb - 1 >= 0 and F[jb - 1] in (1, 2): v += 3.0
                            if F[skip0 + j - 1] in (1, 2): v += 2.0
                        else:
                            if FAM and g == 1 and FAM[skip0 + j - 1]: v += .5 * (FAM[skip0 + j - 1] * 3 - 1)
                            f0 = F[skip0 + j - g]
                            v += 2.5 if f0 == 0 else (1.0 if f0 is None else 0)
                            v += 3.0 * sum(1 for q in range(j - g + 1, j) if F[skip0 + q] == 1)
                    if g > 1 and not HEAD[i - 1] and D[j - 1] < mx - 1e-6: v += .35
                    if v < bestv: bestv, bestg = v, g
                if j >= 1 and i >= 2:
                    q = FAM[skip0 + j - 1] * 3 if FAM else 0
                    for m in range(2, 7 if q else 4):
                        if i - m < 0: break
                        if any(HEAD[i - m:i]): break
                        pv = dp[i - m][j - 1]
                        if pv >= INF: continue
                        es = sum(E[i - m:i])
                        if q: v = pv + .5 * abs(m - q)
                        elif F: v = pv + 3.0 * (m - 1) + (1.0 if F[skip0 + j - 1] is None else 0)
                        else: v = pv + ((1 - es) / max(es, 1)) ** 2 * m + 1.2 * (m - 1)
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
        wordy = (k + 1) in (6, 9, 11, 12, 13, 14, 15, 16, 17)
        if F and wordy:
            FAMv = []
            for i2, (st2, t2) in enumerate(fl):
                nw = len([w for w in t2.split() if len(w) >= 3]) if st2 == 0 and not (i2 and fl[i2 - 1][0] == 1) else 0
                FAMv.append(nw / 3 if nw >= 2 else 0)
        else:
            FAMv = families(sg, words, fl) if F else None
        r = align(units[k], sg, F, hc, FAMv, wordy, [f[1] for f in fl] if words else None) or align(units[k], sg)
        if r: scored.append((r[1], a, r))
    # prefer the -35 dB reading (fewest false splits) unless another fits clearly better
    scored.sort(key=lambda x: x[0]); pref = [x for x in scored if x[1]["db"] == -35]
    pick = scored[0] if not pref or scored[0][0] < .7 * pref[0][0] else pref[0]
    sc, a, (tm, _, skip0) = pick
    M[str(k + 1)] = [[round(t0, 2), round(t1, 2), u["pg"]] + u["box"] for (t0, t1), u in zip(tm, units[k])]
    print(f"   header {tm[0][0]:.1f}-{tm[0][1]:.1f}s; flags {'yes' if words else 'no'}")
    print(f"lesson {k+1}: units {len(units[k])} segs {len(a['segs'])} (db {a['db']}) cost {sc:.2f} intro-skip {skip0} first {tm[0][0]:.1f}s dur {a['dur']}")
# lesson 7: the recording reads rows 1-2, skips rows 3-4, then reads row 5 (إِ هِ وُ هُ ءُ)
# (unit index -> indices of the -35 dB utterances); boxes not read are left out
L7 = {0: [0, 1, 2, 3], 1: [4], 2: [5], 3: [6], 4: [7], 5: [8], 6: [9], 7: [10],
      8: [11], 9: [12], 10: [13], 11: [14], 12: [15], 13: [16], 14: [17],
      30: [18], 31: [19], 32: [20], 33: [21], 34: [22]}
seg7 = [x for x in sync["7"]["alts"] if x["db"] == -35][0]["segs"]
M["7"] = [[round(seg7[v[0]][0], 2), round(seg7[v[-1]][1], 2), units[6][ui]["pg"]] + units[6][ui]["box"] for ui, v in sorted(L7.items())]
print("lesson 7 set by hand:", [(round(u[0], 1), u[2]) for u in M["7"]])
# lessons read word by word: match every box's word (tools/noorania_words.json) to the transcript.
# a box ends when the sheikh says its whole word; the next box starts with the next thing he says.
import difflib
WFILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "noorania_words.json")
def nw(t):
    t = norm(t).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "ء").replace("ئ", "ء").replace("آ", "ا")
    return re.sub(r"[^ء-ي]", "", t)
FIRST = {'ا': ('همز', 'هم', 'حمز'), 'ء': ('همز', 'هم', 'حمز'), 'ب': ('با', 'بى'), 'ت': ('تا', 'تى'), 'ث': ('ثا',), 'ج': ('جيم', 'جي'), 'ح': ('حا', 'حى'), 'خ': ('خا', 'خى'), 'د': ('دال', 'دا'), 'ذ': ('ذال', 'ذا'), 'ر': ('را', 'رى'), 'ز': ('زا', 'زى', 'زاي'), 'س': ('سين',), 'ش': ('شين',), 'ص': ('صاد',), 'ض': ('ضاد',), 'ط': ('طا', 'طى'), 'ظ': ('ظا',), 'ع': ('عين',), 'غ': ('غين',), 'ف': ('فا', 'فى'), 'ق': ('قاف', 'قا'), 'ك': ('كاف', 'كا'), 'ل': ('لام', 'لا'), 'م': ('ميم', 'مين'), 'ن': ('نون',), 'ه': ('ها', 'هى'), 'و': ('واو', 'وا'), 'ي': ('يا', 'يى')}
if os.path.exists(WFILE):
    WORDS = json.load(open(WFILE))
    TITLE = ("الدرس", "تدريب", "عشر", "الاخير", "التاسع", "الحادي", "الثالث", "الرابع", "الخامس", "السادس", "سبق", "الشده", "الشدتين", "كلمه", "السكون", "السقون", "التنوين", "المد", "الثلاثه", "اللين", "الين", "وحرفي", "واحرف", "على", "مع", "في")
    for ks, bw in WORDS.items():
        k = int(ks) - 1; U = units[k]
        if len(U) - 1 != len(bw): print("word list mismatch", ks, len(U) - 1, len(bw)); continue
        asr = os.path.join(os.path.dirname(out), "asr", f"asr-{ks}.json")
        if not os.path.exists(asr): continue
        toks = [(w[0], w[1], nw(w[2])) for sg in json.load(open(asr))["segs"] for w in sg["w"] if nw(w[2])]
        B, T = len(bw), len(toks); tw = [nw(x) for x in bw]
        sim = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio()
        NEG = -1e9
        dp = [[0.0] * (T + 1) for _ in range(B + 1)]; bk = [[0] * (T + 1) for _ in range(B + 1)]
        for i in range(1, B + 1):
            for j in range(0, T + 1):
                best, how = dp[i - 1][j], 1                       # box not heard
                if j and dp[i][j - 1] >= best: best, how = dp[i][j - 1], 2   # token is spelling / other
                if j:
                    sc = sim(tw[i - 1], toks[j - 1][2])
                    if sc >= .7 and dp[i - 1][j - 1] + sc >= best: best, how = dp[i - 1][j - 1] + sc, 3
                dp[i][j] = best; bk[i][j] = how
        match = [None] * B; i, j = B, T
        while i > 0:
            h = bk[i][j]
            if h == 3: match[i - 1] = j - 1; i -= 1; j -= 1
            elif h == 2: j -= 1
            else: i -= 1
        # title: tokens at the start that belong to the lesson name
        tend = 0
        for q, (a, b, t) in enumerate(toks):
            if a > 40: break
            if any(t.startswith(nw(x)) or nw(x) in t for x in TITLE): tend = q
            elif q > tend + 2: break
        # the sheikh reads the whole word last (after spelling it): take the last reading of it,
        # also when the transcript split it in two ("أخا ذا" = أَخَذَ), and never cross the next word's spelling
        for q in range(B):
            if match[q] is None: continue
            lim = next((match[r] for r in range(q + 1, B) if match[r] is not None), T)
            j = match[q] + 1; best = match[q]
            nxt = tw[q + 1][:1] if q + 1 < B else ""
            stops = FIRST.get(nxt, ())
            while j < lim:
                tj = toks[j][2]
                if q + 1 < B and (tj.startswith(tuple(stops)) or sim(tw[q + 1], tj) >= .75): break
                sc1 = sim(tw[q], toks[j][2]); sc2 = sim(tw[q], toks[j][2] + toks[j + 1][2]) if j + 1 < lim else 0
                if sc2 >= .7 and sc2 > sc1: best = j + 1; j += 2; continue
                if sc1 >= .6: best = j
                j += 1
            match[q] = best
        ends = [toks[m][1] if m is not None else None for m in match]
        starts = [None] * B
        for q in range(B):
            prev = match[q - 1] if q and match[q - 1] is not None else (tend if q == 0 else None)
            if prev is not None and prev + 1 < T:
                starts[q] = toks[prev + 1][0]
                # the box starts where the sheikh begins spelling this word (its first letter's name)
                st_ = FIRST.get(tw[q][:1], ())
                hi_ = match[q] if match[q] is not None else min(T - 1, prev + 12)
                for j in range(prev + 1, hi_ + 1):
                    if toks[j][2].startswith(tuple(st_)) or sim(tw[q], toks[j][2]) >= .7: starts[q] = toks[j][0]; break
        # a word the transcript did not catch: it starts where the sheikh names its first letter
        tix = {round(t[0], 3): j for j, t in enumerate(toks)}
        for q in range(B):
            if starts[q] is not None: continue
            lo_ = tix.get(round(starts[q - 1], 3), tend) + 1 if q and starts[q - 1] is not None else tend + 1
            hi_ = next((match[r] for r in range(q + 1, B) if match[r] is not None), T - 1)
            st_ = FIRST.get(tw[q][:1], ())
            for j in range(lo_ + 1, hi_ + 1):
                if toks[j][2].startswith(tuple(st_)): starts[q] = toks[j][0]; break
            if starts[q] is not None and q and ends[q - 1] is None:
                ends[q - 1] = starts[q] - .05
        # boxes not heard in the transcript: share the time between their neighbours by word length
        q = 0
        while q < B:
            if ends[q] is not None and starts[q] is not None: q += 1; continue
            r = q
            while r < B and (ends[r] is None or starts[r] is None): r += 1
            t0 = ends[q - 1] if q else toks[tend][1]
            t1 = starts[r] if r < B and starts[r] is not None else (ends[r] if r < B and ends[r] is not None else toks[-1][1])
            ln = [max(2, len(tw[x])) for x in range(q, r)]; tot = sum(ln); t = t0
            for x, L_ in zip(range(q, r), ln):
                d_ = (t1 - t0) * L_ / tot; starts[x] = t if starts[x] is None else starts[x]; ends[x] = t + d_ if ends[x] is None else ends[x]; t += d_
            q = r
        for q in range(1, B):
            if starts[q] < starts[q - 1]: starts[q] = starts[q - 1] + .05
        head = U[0]
        M[ks] = [[round(toks[0][0] if toks else 0, 2), round(max(.5, starts[0] - .1), 2), head["pg"]] + head["box"]] + \
                [[round(starts[q], 2), round(max(ends[q], starts[q] + .3), 2), U[q + 1]["pg"]] + U[q + 1]["box"] for q in range(B)]
        heard = sum(1 for m in match if m is not None)
        print(f"lesson {ks}: matched {heard} of {B} words by text; title ends {starts[0]:.1f}s")
# never start or end a box in the middle of a spoken word
for ks in ["6", "9", "11", "13", "14", "15", "16", "17"]:
    U = M.get(ks); asr = os.path.join(os.path.dirname(out), "asr", f"asr-{ks}.json")
    if not U or not os.path.exists(asr): continue
    W_ = [w for sg in json.load(open(asr))["segs"] for w in sg["w"] if w[1] - w[0] > .05]
    moved = 0
    for i in range(1, len(U)):
        t = U[i][0]
        for w0, w1, _ in W_:
            if w0 + .04 < t < w1 - .04:
                nt = round(w0 - .04, 2) if (t - w0) < (w1 - t) else round(w1 + .02, 2)
                if U[i - 1][0] + .2 < nt < (U[i + 1][0] - .2 if i + 1 < len(U) else 1e9): U[i][0] = nt; moved += 1
                break
    for i in range(len(U)):
        nx = U[i + 1][0] if i + 1 < len(U) else None
        if nx is not None and U[i][1] > nx: U[i][1] = round(nx - .02, 2)
        for w0, w1, _ in W_:
            if w0 + .04 < U[i][1] < w1 - .04 and (nx is None or w1 < nx): U[i][1] = round(w1 + .02, 2); break
    print(f"lesson {ks}: {moved} box starts moved off mid-word")
# lesson 4: every letter is read in five utterances (X fatha Xa / X kasra Xi / Xa Xi / X damma Xu / Xa Xi Xu):
# fatha box = 1st, kasra box = 2nd+3rd, damma box = 4th+5th. From dal on the sheikh reads each letter's three
# boxes in one breath without spelling: that utterance is shared out over the three boxes.
U4 = list(units[3])
if len(U4) == 84:   # the detector missed the last box of row 3 (kaf damma)
    r3 = [u for u in U4 if u["pg"] == 11 and abs(u["box"][1] - U4[17]["box"][1]) < .01]
    U4.insert(U4.index(r3[-1]) + 1, {"pg": 11, "box": [round(2 * r3[-1]["box"][0] - r3[-2]["box"][0], 4)] + r3[-1]["box"][1:]})
seg4 = [x for x in sync["4"]["alts"] if x["db"] == -30][0]["segs"]
if len(U4) == 85 and len(seg4) == 98:
    T4 = [(seg4[0][0], seg4[5][1])]
    i = 6
    for L in range(16):
        a, b, c, d, e = seg4[i:i + 5]; i += 5
        T4 += [(a[0], a[1]), (b[0], c[1]), (d[0], e[1])]
    for L in range(12):
        s0, s1 = seg4[i]; i += 1; st = (s1 - s0) / 3
        T4 += [(s0 + q * st, s0 + (q + 1) * st) for q in range(3)]
    M["4"] = [[round(t0, 2), round(t1, 2), u["pg"]] + u["box"] for (t0, t1), u in zip(T4, U4)]
    print("lesson 4 set by its reading pattern:", len(M["4"]), "boxes")
else:
    print("lesson 4: unexpected layout", len(U4), len(seg4))
import time
M["_v"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
json.dump(M, open(out, "w"), separators=(",", ":"))
