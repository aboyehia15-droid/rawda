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
                if first: first = False; units[0].insert(0, hu)
                else: cur += 1; units[min(cur, 16)].append(hu)
                continue
            x, y, w, h = c
            wt = 1.0 if w < .2 else max(1.0, w / .085)
            units[min(cur, 16)].append({"pg": pg, "box": [x, y, w, h], "wt": wt})
print("lessons starting with their heading:", sum(1 for u in units if u and u[0].get("head")))
print("headings ->", cur + 1, "lessons; units:", [len(u) for u in units])

def align(U, segs):
    K, N = len(U), len(segs)
    if K == 0 or N == 0: return []
    W = [u["wt"] for u in U]
    best = None
    for skip0 in range(0, min(8, N - 1)):
        S = segs[skip0:]
        n = len(S)
        tot = sum(b - a for a, b in S); c = tot / sum(W)
        G = max(8, math.ceil(3 * n / K))
        INF = 1e18
        # dp[i][j]: first i units used first j segments
        dp = [[INF] * (n + 1) for _ in range(K + 1)]; bk = [[0] * (n + 1) for _ in range(K + 1)]
        dp[0][0] = 0
        for i in range(1, K + 1):
            exp = c * W[i - 1]
            lo = 1; hi = n
            for j in range(lo, hi + 1):
                bestv, bestg = INF, 0
                d = 0.0
                for g in range(1, G + 1):
                    if j - g < 0: break
                    a, b = S[j - g]
                    d += b - a
                    pv = dp[i - 1][j - g]
                    if pv >= INF: continue
                    v = pv + ((d - exp) / max(exp, .25)) ** 2 + .15 * (g - 1)
                    if v < bestv: bestv, bestg = v, g
                # one segment shared by several units (read without a pause)
                if j >= 1:
                    a, b = S[j - 1]; d = b - a
                    for m in range(2, 5):
                        if i - m < 0: break
                        pv = dp[i - m][j - 1]
                        if pv >= INF: continue
                        ws = W[i - m:i]; tw = sum(ws)
                        v = pv + sum(((d * w / tw) - c * w) / max(c * w, .25) for w in ws) ** 2 / m + .8 * (m - 1)
                        if v < bestv: bestv, bestg = v, -m
                dp[i][j] = bestv; bk[i][j] = bestg
        # allow skipping trailing segments
        for j in range(1, n + 1):
            v = dp[K][j] + .6 * (n - j) + .6 * skip0
            if best is None or v < best[0]: best = (v, skip0, j, bk, S)
    if best is None or best[0] >= 1e17: return None
    v, skip0, j, bk, S = best
    res = []; i = K
    while i > 0:
        g = bk[i][j]
        if g < 0:
            m = -g; a, b = S[j - 1]; ws = W[i - m:i]; tw = sum(ws); t = b
            for w in reversed(ws):
                d = (b - a) * w / tw; res.append((t - d, t)); t -= d
            j -= 1; i -= m
        else:
            res.append((S[j - g][0], S[j - 1][1])); j -= g; i -= 1
    res.reverse()
    return res, v / K, skip0

M = {}
for k in range(17):
    alts = sync.get(str(k + 1), {}).get("alts", [])
    if not alts or not units[k]: print(k + 1, "no data"); continue
    scored = []
    for a in alts:
        r = align(units[k], a["segs"])
        if r: scored.append((r[1], a, r))
    scored.sort(key=lambda x: x[0]); sc, a, (tm, _, skip0) = scored[0]
    M[str(k + 1)] = [[round(t0, 2), round(t1, 2), u["pg"]] + u["box"] for (t0, t1), u in zip(tm, units[k])]
    print(f"lesson {k+1}: units {len(units[k])} segs {len(a['segs'])} (db {a['db']}) cost {sc:.2f} intro-skip {skip0} first {tm[0][0]:.1f}s dur {a['dur']}")
json.dump(M, open(out, "w"), separators=(",", ":"))
