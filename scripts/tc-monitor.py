#!/usr/bin/env python3
# Trypnocore v6 — Terminal Comms & Board Monitor
# Streams #lobby, #ops, #mud, and Kanban board status directly to a terminal pane.
# Zero Electron GUI / browser overhead.
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

db_path = get_db_path()
if not os.path.exists(db_path):
    print(f"\033[1;31m[ERROR] Hub database not found at {db_path}\033[0m")
    sys.exit(1)

def clear_screen():
    sys.stdout.write("\033[2J\033[H")

def render():
    clear_screen()
    print("\033[1;36m" + "=" * 80 + "\033[0m")
    print("\033[1;37m  TRYPNOCORE v6 — FLEET COMMS & KANBAN MONITOR (Terminal Engine)\033[0m")
    print("\033[1;36m" + "=" * 80 + "\033[0m")

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        cur = con.cursor()

        # 1. Kanban Board Counts
        try:
            cur.execute('SELECT "column", COUNT(*) FROM cards GROUP BY "column"')
            counts = dict(cur.fetchall())
            b = counts.get("backlog", 0)
            r = counts.get("ready", 0)
            p = counts.get("in_progress", 0)
            rv = counts.get("review", 0)
            d = counts.get("done", 0)
            bl = counts.get("blocked", 0)

            print(f"\033[1;33m[KANBAN BOARD]\033[0m "
                  f"Backlog: \033[1m{b}\033[0m | "
                  f"Ready: \033[1m{r}\033[0m | "
                  f"In Progress: \033[1;32m{p}\033[0m | "
                  f"Review: \033[1;35m{rv}\033[0m | "
                  f"Done: \033[1;34m{d}\033[0m | "
                  f"Blocked: \033[1;31m{bl}\033[0m")
            print("\033[38;5;240m" + "-" * 80 + "\033[0m")
        except Exception:
            pass

        # 2. Recent Messages in Channels
        print("\033[1;32m[ACTIVE CHANNELS: #ops | #lobby | #mud]\033[0m")
        cur.execute("""
            SELECT ts, sender, to_target, body 
            FROM messages 
            WHERE to_target IN ('lobby', 'ops', 'mud') OR to_kind = 'channel'
            ORDER BY rowid DESC 
            LIMIT 15
        """)
        rows = cur.fetchall()
        if not rows:
            print("  (No messages posted to fleet channels yet)")
        else:
            for ts, sender, to_target, body in reversed(rows):
                t_str = ts[11:19] if ts and len(ts) >= 19 else "--:--:--"
                ch = to_target if to_target.startswith("#") else f"#{to_target}"
                first_line = body.split("\n")[0][:75]
                print(f"\033[38;5;244m[{t_str}]\033[0m \033[1;35m{ch:<8}\033[0m \033[1;33m{sender:<16}\033[0m \033[37m{first_line}\033[0m")

        con.close()
    except Exception as e:
        print(f"\033[31m[DB READ ERROR] {e}\033[0m")

    print("\033[1;36m" + "=" * 80 + "\033[0m")
    print("\033[38;5;244mPress Ctrl+C to exit monitor. Auto-refreshes every 2s.\033[0m")

if __name__ == "__main__":
    try:
        if "--once" in sys.argv:
            render()
            sys.exit(0)
        while True:
            render()
            time.sleep(2)
    except KeyboardInterrupt:
        sys.exit(0)
