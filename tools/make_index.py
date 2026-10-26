"""books/index.json and voices/index.json: lists the screens read from the program's own site (no GitHub API limit)."""
import json, os, subprocess
for d, ext in (("books", (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif")), ("voices", (".json",))):
    if not os.path.isdir(d): continue
    out = []
    for n in sorted(os.listdir(d)):
        p = f"{d}/{n}"
        if n == "index.json" or not os.path.isfile(p) or not n.lower().endswith(ext): continue
        sha = subprocess.run(["git", "hash-object", p], capture_output=True, text=True).stdout.strip()
        out.append({"name": n, "path": p, "sha": sha, "size": os.path.getsize(p)})
    json.dump(out, open(f"{d}/index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(d, len(out))
