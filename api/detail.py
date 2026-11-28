from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import concurrent.futures

def req_json(url, method="GET", payload=None, timeout=6):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 500, None

def get_ip_detail(ip):
    if not ip or ip in ("-", "N/A", "Unknown") or ":" in ip:
        return {"country": "Unknown", "region": "", "city": "", "isp": ""}
    st, data = req_json(f"https://ipwho.is/{ip}", timeout=5)
    if st == 200 and data and data.get("success"):
        conn = data.get("connection") or {}
        return {
            "country": data.get("country", "Unknown"),
            "region": data.get("region", ""),
            "city": data.get("city", ""),
            "isp": conn.get("isp") or conn.get("org") or ""
        }
    return {"country": "Unknown", "region": "", "city": "", "isp": ""}

def get_wearing(uid):
    st, av = req_json(f"https://avatar.roblox.com/v1/users/{uid}/avatar", timeout=5)
    if st != 200 or not av:
        return []
    assets = av.get("assets", [])
    if not assets:
        return []
    ids = [str(a["id"]) for a in assets if a.get("id")]
    thumb_map = {}
    if ids:
        _, th = req_json(f"https://thumbnails.roblox.com/v1/assets?assetIds={','.join(ids[:30])}&size=150x150&format=Png&isCircular=false", timeout=5)
        if th and th.get("data"):
            for t in th["data"]:
                thumb_map[t.get("targetId")] = t.get("imageUrl", "")
    return [{"id": a["id"], "name": a.get("name", "Item"), "image": thumb_map.get(a["id"], "")} for a in assets]

def get_badges(uid):
    st, bg = req_json(f"https://badges.roblox.com/v1/users/{uid}/badges?limit=25&sortOrder=Desc", timeout=5)
    if st != 200 or not bg or not bg.get("data"):
        return []
    items = bg["data"]
    ids = [str(b["id"]) for b in items if b.get("id")]
    thumb_map = {}
    if ids:
        _, th = req_json(f"https://thumbnails.roblox.com/v1/badges/icons?badgeIds={','.join(ids[:25])}&size=150x150&format=Png", timeout=5)
        if th and th.get("data"):
            for t in th["data"]:
                thumb_map[t.get("targetId")] = t.get("imageUrl", "")
    return [{"id": b["id"], "name": b.get("name", "Badge"), "image": thumb_map.get(b["id"], "")} for b in items]

def get_groups(uid):
    st, gr = req_json(f"https://groups.roblox.com/v1/users/{uid}/groups/roles", timeout=5)
    if st != 200 or not gr or not gr.get("data"):
        return []
    out = []
    for g in gr["data"]:
        grp = g.get("group") or {}
        role = g.get("role") or {}
        out.append({
            "id": grp.get("id"),
            "name": grp.get("name", "Group"),
            "members": grp.get("memberCount", 0),
            "role": role.get("name", "Member"),
            "rank": role.get("rank", 0)
        })
    return out

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            usn = (body.get("usn") or "").strip()
            ip = (body.get("ip") or "").strip()

            uid = None
            if usn:
                st, udata = req_json("https://users.roblox.com/v1/usernames/users", "POST", {"usernames": [usn], "excludeBannedUsers": False})
                if st == 200 and udata and udata.get("data"):
                    uid = udata["data"][0]["id"]

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                f_ip = ex.submit(get_ip_detail, ip)
                f_wear = ex.submit(get_wearing, uid) if uid else None
                f_badge = ex.submit(get_badges, uid) if uid else None
                f_group = ex.submit(get_groups, uid) if uid else None

                res = {
                    "ip_info": f_ip.result(),
                    "wearing": f_wear.result() if f_wear else [],
                    "badges": f_badge.result() if f_badge else [],
                    "groups": f_group.result() if f_group else []
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
