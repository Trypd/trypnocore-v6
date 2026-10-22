#!/usr/bin/env python3
"""
Trypnocore v6 — Unified Fleet CLI (Serverless Edition)
Interacts directly with hub.db using SQLite (zero server daemon overhead).

Usage:
  tc send <#channel> "<message>"
  tc read <#channel> [limit]
  tc board [list|claim|move|create] ...
  tc mud "<action>"
"""
import sys, os, sqlite3, json, datetime

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

def get_db():
    db_file = get_db_path()
    if not os.path.exists(db_file):
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
    return sqlite3.connect(db_file, timeout=5.0)

def get_agent():
    for var in ["AGENT_SLUG", "TC_AGENT_SLUG", "CLAUDE_AGENT_NAME", "AGENT_NAME"]:
        if var in os.environ and os.environ[var].strip():
            return os.environ[var].strip()
    cwd = os.getcwd()
    base = os.path.basename(cwd).lower()
    return base if base else "peer-node"

def cmd_send(channel, body):
    ch = channel.lstrip("#")
    agent = get_agent()
    con = get_db()
    cur = con.cursor()
    msg_id = f"msg_{int(datetime.datetime.now().timestamp()*1000)}"
    now = datetime.datetime.utcnow().isoformat() + "Z"
    cur.execute("""
        INSERT INTO messages (id, ts, type, sender, to_kind, to_target, body, mentions, priority, meta, hops)
        VALUES (?, ?, 'chat', ?, 'channel', ?, ?, '[]', 'normal', '{}', 0)
    """, (msg_id, now, agent, ch, body))
    con.commit()
    con.close()
    print(f"\033[1;32m[SENT]\033[0m #{ch} from {agent}: {body[:65]}...")

def cmd_read(channel, limit=10):
    ch = channel.lstrip("#")
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        SELECT ts, sender, body FROM messages 
        WHERE to_target = ? OR to_target = ? 
        ORDER BY rowid DESC LIMIT ?
    """, (ch, f"#{ch}", limit))
    rows = cur.fetchall()
    con.close()
    print(f"\033[1;36m=== #{ch} (Last {len(rows)} Messages) ===\033[0m")
    for ts, sender, body in reversed(rows):
        t = ts[11:19] if len(ts) >= 19 else ts
        print(f"\033[38;5;244m[{t}]\033[0m \033[1;33m{sender:<16}\033[0m {body}")

def cmd_board(args):
    con = get_db()
    cur = con.cursor()
    sub = args[0] if args else "list"
    if sub == "list":
        cur.execute('''
            SELECT c.id, c."column", c.title, GROUP_CONCAT(ca.agent, ', ') as assignees
            FROM cards c
            LEFT JOIN card_assignees ca ON c.id = ca.card
            GROUP BY c.id
            ORDER BY c."column", c.created_ts
        ''')
        cards = cur.fetchall()
        print("\033[1;36m=== TRYPNOCORE v6 KANBAN BOARD ===\033[0m")
        if not cards:
            print("  (Board is empty)")
        for cid, col, title, assignees in cards:
            asg = assignees if assignees else "unassigned"
            print(f"[{col:<11}] \033[1m{cid}\033[0m: {title} (\033[38;5;244m{asg}\033[0m)")
    elif sub == "claim" and len(args) > 1:
        cid = args[1]
        agent = get_agent()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        cur.execute("INSERT OR IGNORE INTO card_assignees (card, agent, assigned_ts) VALUES (?, ?, ?)", (cid, agent, now))
        cur.execute('UPDATE cards SET "column" = "in_progress", updated_ts = ? WHERE id = ?', (now, cid))
        con.commit()
        print(f"Claimed {cid} -> in_progress by {agent}")
    elif sub == "move" and len(args) > 2:
        cid, col = args[1], args[2]
        now = datetime.datetime.utcnow().isoformat() + "Z"
        cur.execute('UPDATE cards SET "column" = ?, updated_ts = ? WHERE id = ?', (col, now, cid))
        con.commit()
        print(f"Moved {cid} -> {col}")
    elif sub == "create" and len(args) > 1:
        title = args[1]
        body = args[2] if len(args) > 2 else ""
        cid = f"v6-{int(datetime.datetime.now().timestamp()%100000):05d}"
        agent = get_agent()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        src = "operator" if agent == "operator" else "agent"
        cur.execute("""
            INSERT INTO cards (id, title, body, "column", creator, source, labels, thread_id, due, created_ts, updated_ts, roles)
            VALUES (?, ?, ?, 'backlog', ?, ?, '[]', NULL, NULL, ?, ?, '{}')
        """, (cid, title, body, agent, src, now, now))
        cur.execute("INSERT INTO card_assignees (card, agent, assigned_ts) VALUES (?, ?, ?)", (cid, agent, now))
        con.commit()
        print(f"Created card {cid} in backlog: {title}")
    con.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tc [send|read|board|mud] ...")
        sys.exit(0)
    action = sys.argv[1]
    if action == "send" and len(sys.argv) >= 4:
        cmd_send(sys.argv[2], " ".join(sys.argv[3:]))
    elif action == "read":
        ch = sys.argv[2] if len(sys.argv) > 2 else "lobby"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 10
        cmd_read(ch, limit)
    elif action == "board":
        cmd_board(sys.argv[2:])
    elif action == "mud":
        cmd_send("mud", " ".join(sys.argv[2:]))
    else:
        print("Unknown command or missing arguments. Run without arguments for help.")
