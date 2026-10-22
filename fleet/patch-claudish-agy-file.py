"""Patch claudish 12.3.0's AGY token store: macOS keychain -> grafted file on WSL.

claudish 12.3.0 hardcoded the Antigravity shared token store to the macOS
keychain (process.platform !== 'darwin' -> throw). The Trypnocore graft keeps
the token in ~/.claudish/antigravity-token.txt with a refresh daemon. This
patch makes the three store functions fall back to that file off-darwin.

Idempotent. Re-run after claudish updates (dist/index.js is regenerated).
Run from WSL: python3 /mnt/c/Trypnocore/fleet/patch-claudish-agy-file.py
"""
from pathlib import Path

P = Path("/usr/lib/node_modules/claudish/dist/index.js")
code = P.read_text()

PATCHED_MARK = "Trypnocore graft"
if PATCHED_MARK in code:
    print("already patched")
    raise SystemExit(0)

# 1) readStore: file fallback on non-darwin
old_read = """function defaultReadStore() {
  if (process.platform !== "darwin") {
    logStderr("[Antigravity] Shared token store is macOS-only for now (other keyring backends are a follow-up).");
    return null;
  }"""
new_read = """function defaultReadStore() {
  if (process.platform !== "darwin") {
    // Trypnocore graft: read the token file the WSL refresh daemon maintains.
    try {
      const f = join10(homedir10(), ".claudish", "antigravity-token.txt");
      if (existsSync8(f)) { const v = readFileSync8(f, "utf8").trim(); return v || null; }
    } catch {}
    logStderr("[Antigravity] Shared token store is macOS-only for now (other keyring backends are a follow-up).");
    return null;
  }"""
assert code.count(old_read) == 1, "read anchor missing"
code = code.replace(old_read, new_read)

# 2) resolveValidToken: allow non-darwin when the graft file exists
old_throw = """  if (process.platform !== "darwin") {
    throw terminalCredentialError("[Antigravity] The shared Antigravity token store is macOS-only for now. " + "Use g@<model> with GEMINI_API_KEY on this platform.");
  }"""
new_throw = """  if (process.platform !== "darwin") {
    // Trypnocore graft: allow when the token file exists (refresh daemon owns it).
    if (!existsSync8(join10(homedir10(), ".claudish", "antigravity-token.txt"))) {
      throw terminalCredentialError("[Antigravity] The shared Antigravity token store is macOS-only for now. " + "Use g@<model> with GEMINI_API_KEY on this platform.");
    }
  }"""
assert code.count(old_throw) == 2, "throw anchor missing"
code = code.replace(old_throw, new_throw)

# 3) writeStore: persist to the file on non-darwin
old_write = """function defaultWriteStore(rawValue) {
  if (process.platform !== "darwin") {
    throw new Error("[Antigravity] Cannot write the shared token store on a non-macOS platform.");
  }"""
new_write = """function defaultWriteStore(rawValue) {
  if (process.platform !== "darwin") {
    // Trypnocore graft: persist to the token file on non-macOS.
    const dir = join10(homedir10(), ".claudish");
    mkdirSync2(dir, { recursive: true });
    writeFileSync3(join10(dir, "antigravity-token.txt"), rawValue, { mode: 0o600 });
    invalidateReadStoreMemo();
    return;
  }"""
assert code.count(old_write) == 1, "write anchor missing"
code = code.replace(old_write, new_write)

P.write_text(code)
print("patched 3 sites in", P)
