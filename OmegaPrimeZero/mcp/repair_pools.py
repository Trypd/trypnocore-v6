import pathlib
import re

from hyperon import MeTTa

PAT = re.compile(r"\\([^ntr\"\\])")


def fix(text: str) -> str:
    prev = None
    cur = text
    for _ in range(4):
        if cur == prev:
            break
        prev = cur
        cur = PAT.sub(r"\1", cur)
    return cur


for pool in sorted(pathlib.Path(r"C:\Trypnocore\OmegaPrimeZero\out\metta").glob("pool-*.metta")):
    text = pool.read_text(encoding="utf-8", errors="replace")
    fixed = fix(text)
    if fixed != text:
        pool.write_text(fixed, encoding="utf-8")
    try:
        MeTTa().run(fixed)
        print(pool.name, "repaired+loads" if fixed != text else "loads")
    except Exception as e:
        print(pool.name, "STILL BROKEN:", str(e)[:80])
