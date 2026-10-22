"""Align Noorania speech segments to the cells of each lesson -> noorania/map.json
units: cells in reading order (rows top->bottom, cells right->left), split into lessons at the lesson headings.
DP: every unit takes one or more consecutive speech segments; a few segments may be skipped at the start
(lesson title / introduction) and at the end; cost = squared deviation from the expected duration."""
import json, sys, math
cells = json.load(open(sys.argv[1])); sync = json.load(open(sys.argv[2])); out = sys.argv[3]
# headings the detector missed: page -> row index before which a heading sits
EXTRA_H = {"24": 6, "26": 8}
LAST_ROWS = {"29": 4}
units = [[] for _ in range(17)]; cur = 0; first = True
for pg in range(7, 30):
    rows = cells.get(str(pg), [])
    if str(pg) in LAST_ROWS: rows = rows[:LAST_ROWS[str(pg)]]
    for ri, row in enumerate(rows):
        if EXTRA_H.get(str(pg)) == ri: cur += 1
        for c in row:
            if c[0] == 'H':
                if first: first = False
                else: cur += 1
                continue
            x, y, w, h = c
            wt = 1.0 if w < .2 else max(1.0, w / .085)
            units[min(cur, 16)].append({"pg": pg, "box": [x, y, w, h], "wt": wt})
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
        G = 8
        INF = 1e18
        # dp[i][j]: first i units used first j segments
        dp = [[INF] * (n + 1) for _ in range(K + 1)]; bk = [[0] * (n + 1) for _ in range(K + 1)]
        dp[0][0] = 0
        for i in range(1, K + 1):
            exp = c * W[i - 1]
            lo = max(i, 1); hi = n - (K - i) if True else n
            for j in range(lo, hi + 1):
                bestv, bestg = INF, 0
                d = 0.0
                for g in range(1, G + 1):
                    if j - g < i - 1: break
                    a, b = S[j - g]
                    d += b - a
                    pv = dp[i - 1][j - g]
                    if pv >= INF: continue
                    v = pv + ((d - exp) / max(exp, .25)) ** 2 + .15 * (g - 1)
                    if v < bestv: bestv, bestg = v, g
                dp[i][j] = bestv; bk[i][j] = bestg
        # allow skipping trailing segments
        for j in range(K, n + 1):
            v = dp[K][j] + .6 * (n - j) + .6 * skip0
            if best is None or v < best[0]: best = (v, skip0, j, bk, S)
    v, skip0, j, bk, S = best
    res = []; i = K
    while i > 0:
        g = bk[i][j]; res.append((S[j - g][0], S[j - 1][1])); j -= g; i -= 1
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
