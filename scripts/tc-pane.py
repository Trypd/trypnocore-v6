#!/usr/bin/env python3
# Trypnocore v6 — single-channel / kanban pane monitor
# Usage: tc-pane.py lobby|mud|ops|kanban
import os, sys, time, sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def get_db_path():
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        if os.path.exists("/mnt/c/Users/Trypd/AppData/Local"):
            appdata = "/mnt/c/Users/Trypd/AppData/Local"
        else:
            appdata = os.path.expanduser("~/AppData/Local")
    return os.path.join(appdata, "Trypnocore", "hub.db")

def clear_screen():
    sys.stdout.write("\033[2J\033[H")

def render_channel(cur, channel):
    cur.execute("""
        SELECT ts, sender, body FROM messages
        WHERE to_target = ? ORDER BY rowid DESC LIMIT 25
    """, (channel,))
    rows = cur.fetchall()
    if not rows:
        print("  (no messages yet)")
    else:
        for ts, sender, body in reversed(rows):
            t_str = ts[11:19] if ts and len(ts) >= 19 else "--:--:--"
            first_line = body.split("\n")[0][:95]
            print(f"\033[38;5;244m[{t_str}]\033[0m \033[1;33m{sender:<18}\033[0m \033[37m{first_line}\033[0m")

def render_kanban(cur):
    cur.execute('SELECT "column", COUNT(*) FROM cards GROUP BY "column"')
    counts = dict(cur.fetchall())
    print(f"Backlog: \033[1m{counts.get('backlog',0)}\033[0m | "
          f"Ready: \033[1m{counts.get('ready',0)}\033[0m | "
          f"In Progress: \033[1;32m{counts.get('in_progress',0)}\033[0m | "
          f"Review: \033[1;35m{counts.get('review',0)}\033[0m | "
          f"Done: \033[1;34m{counts.get('done',0)}\033[0m | "
          f"Blocked: \033[1;31m{counts.get('blocked',0)}\033[0m")
    print("\033[38;5;240m" + "-" * 60 + "\033[0m")
    cur.execute('SELECT id, "column", title, creator FROM cards ORDER BY updated_ts DESC LIMIT 15')
    for cid, col, title, creator in cur.fetchall():
        print(f"\033[1;36m{cid}\033[0m \033[38;5;244m[{col}]\033[0m \033[37m{title[:60]}\033[0m \033[38;5;244m({creator})\033[0m")

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "lobby"
    titles = {"lobby": "#LOBBY", "mud": "#MUD", "ops": "#OPS", "kanban": "KANBAN BOARD"}
    title = titles.get(which, which.upper())
    db_path = get_db_path()
    while True:
        clear_screen()
        print("\033[1;36m" + "=" * 60 + "\033[0m")
        print(f"\033[1;37m  TRYPNOCORE v6 — {title}\033[0m")
        print("\033[1;36m" + "=" * 60 + "\033[0m")
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
            cur = con.cursor()
            if which == "kanban":
                render_kanban(cur)
            else:
                render_channel(cur, which)
            con.close()
        except Exception as e:
            print(f"\033[31m[DB READ ERROR] {e}\033[0m")
        print("\033[1;36m" + "=" * 60 + "\033[0m")
        print("\033[38;5;244mCtrl+C exits. Refresh 2s.\033[0m")
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
