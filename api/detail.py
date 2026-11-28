from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse

def fetch_json(url, method="GET", payload=None, timeout=6):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            body = {}

        usn = (body.get("usn") or "").strip()
        ip = (body.get("ip") or "").strip()

        ip_info = {"country": "", "region": "", "city": "", "isp": "-"}
        if ip and ip != "-" and not ip.startswith("127."):
            try:
                ip_res = fetch_json(f"http://ip-api.com/json/{urllib.parse.quote(ip)}?fields=status,country,regionName,city,isp", timeout=4)
                if ip_res.get("status") == "success":
                    ip_info = {
                        "country": ip_res.get("country", ""),
                        "region": ip_res.get("regionName", ""),
                        "city": ip_res.get("city", ""),
                        "isp": ip_res.get("isp", "-")
                    }
            except Exception:
                pass

        user_id = None
        if usn:
            try:
                u_res = fetch_json("https://users.roblox.com/v1/usernames/users", method="POST", payload={"usernames": [usn], "excludeBannedUsers": False})
                if u_res.get("data"):
                    user_id = u_res["data"][0].get("id")
            except Exception:
                pass

        wearing, badges, groups = [], [], []
        if user_id:
            try:
                av_res = fetch_json(f"https://avatar.roblox.com/v1/users/{user_id}/avatar")
                assets = av_res.get("assets", [])[:20]
                asset_ids = [a["id"] for a in assets if a.get("id")]
                thumb_map = {}
                if asset_ids:
                    t_res = fetch_json(f"https://thumbnails.roblox.com/v1/assets?assetIds={','.join(map(str, asset_ids))}&size=150x150&format=Png&isCircular=false")
                    for t in t_res.get("data", []):
                        thumb_map[t.get("targetId")] = t.get("imageUrl", "")
                for a in assets:
                    aid = a.get("id")
                    wearing.append({
                        "id": aid,
                        "name": a.get("name", "Item"),
                        "image": thumb_map.get(aid, "")
                    })
            except Exception:
                pass

            try:
                b_res = fetch_json(f"https://badges.roblox.com/v1/users/{user_id}/badges?limit=15&sortOrder=Desc")
                b_list = b_res.get("data", [])
                b_ids = [b["id"] for b in b_list if b.get("id")]
                b_thumbs = {}
                if b_ids:
                    bt_res = fetch_json(f"https://thumbnails.roblox.com/v1/badges/icons?badgeIds={','.join(map(str, b_ids))}&size=150x150&format=Png")
                    for t in bt_res.get("data", []):
                        b_thumbs[t.get("targetId")] = t.get("imageUrl", "")
                for b in b_list:
                    bid = b.get("id")
                    badges.append({
                        "id": bid,
                        "name": b.get("name", "Badge"),
                        "image": b_thumbs.get(bid, "")
                    })
            except Exception:
                pass

            try:
                g_res = fetch_json(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles")
                for g in g_res.get("data", [])[:20]:
                    grp = g.get("group", {})
                    role = g.get("role", {})
                    groups.append({
                        "name": grp.get("name", "Group"),
                        "members": grp.get("memberCount", 0),
                        "role": role.get("name", "Member")
                    })
            except Exception:
                pass

        out = json.dumps({
            "user_id": user_id,
            "ip_info": ip_info,
            "wearing": wearing,
            "badges": badges,
            "groups": groups
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)
