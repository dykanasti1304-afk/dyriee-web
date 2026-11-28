from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
VERIFIED_IDS = [102611803, 1567446]
SPECIAL_ASSETS = {
    139607718: ("Korblox Deathspeaker", 17000),
    139607673: ("Korblox Deathspeaker", 17000),
    139607570: ("Korblox Deathspeaker", 17000),
    139607625: ("Korblox Deathspeaker", 17000),
    139607770: ("Korblox Deathspeaker", 17000),
    1509305368: ("Headless Horseman", 31000),
    134082579: ("Headless Horseman", 31000),
    1402432199: ("Violet Valkyrie", 50000),
    124730194: ("Blackvalk", 25000),
    151789690: ("Ice Valkyrie", 45000),
    1365767: ("Valkyrie Helm", 20000),
    8329438: ("Stitchface", 4000),
    131144461: ("Extreme Headphones", 7500),
    1235488: ("Clockwork's Headphones", 15000),
    1029025: ("Workclock Headphones", 3000),
}

def req_json(url, method="GET", body=None):
    try:
        req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception:
        return 0, {}

def get_detail(usn, ip=""):
    out = {
        "usn": usn,
        "ip": ip,
        "uid": None,
        "created": "-",
        "description": "",
        "is_banned": False,
        "is_private": False,
        "has_verified": False,
        "total_rap": 0,
        "bundle_value": 0,
        "items": [],
        "avatar": "",
        "location": "-"
    }
    if ip:
        st_ip, ip_data = req_json(f"http://ip-api.com/json/{ip}?fields=status,country,city")
        if st_ip == 200 and ip_data.get("status") == "success":
            out["location"] = f"{ip_data.get('country', '')} ({ip_data.get('city', '')})".strip(" ()")

    payload = json.dumps({"usernames": [usn], "excludeBannedUsers": False}).encode("utf-8")
    st_u, u_data = req_json("https://users.roblox.com/v1/usernames/users", "POST", payload)
    users = u_data.get("data", []) if isinstance(u_data, dict) else []
    if not users:
        return out

    uid = users[0].get("id")
    out["uid"] = uid

    st_p, prof = req_json(f"https://users.roblox.com/v1/users/{uid}")
    if st_p == 200 and isinstance(prof, dict):
        out["created"] = (prof.get("created") or "-")[:10]
        out["description"] = prof.get("description") or ""
        out["is_banned"] = bool(prof.get("isBanned"))

    st_th, th = req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false")
    if st_th == 200 and isinstance(th, dict) and th.get("data"):
        out["avatar"] = th["data"][0].get("imageUrl", "")

    st_av, av = req_json(f"https://avatar.roblox.com/v1/users/{uid}/avatar")
    found_names = set()
    if st_av == 200 and isinstance(av, dict):
        for a in av.get("assets", []):
            aid = a.get("id")
            if aid in VERIFIED_IDS:
                out["has_verified"] = True
            if aid in SPECIAL_ASSETS:
                nm, val = SPECIAL_ASSETS[aid]
                if nm not in found_names:
                    found_names.add(nm)
                    out["bundle_value"] += val
                    out["items"].append({"name": nm, "rap": val, "type": "Special / Bundle"})

    if not out["has_verified"]:
        for vid in VERIFIED_IDS:
            st_v, vd = req_json(f"https://inventory.roblox.com/v1/users/{uid}/items/Asset/{vid}")
            if st_v == 200 and isinstance(vd, dict) and len(vd.get("data", [])) > 0:
                out["has_verified"] = True
                break

    st_col, col = req_json(f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100")
    if st_col == 403:
        out["is_private"] = True
    elif st_col == 200 and isinstance(col, dict):
        for it in col.get("data", []):
            nm = it.get("name") or "Limited Item"
            rap = int(it.get("recentAveragePrice") or 0)
            out["total_rap"] += rap
            out["items"].append({"name": nm, "rap": rap, "type": "Limited"})

    st_b, bd = req_json(f"https://catalog.roblox.com/v1/users/{uid}/bundles?limit=100&sortOrder=Desc")
    if st_b == 200 and isinstance(bd, dict):
        for b in bd.get("data", []):
            bid = b.get("id")
            bname = b.get("name", "")
            if bid == 192 or "korblox" in bname.lower():
                if "Korblox Deathspeaker" not in found_names:
                    found_names.add("Korblox Deathspeaker")
                    out["bundle_value"] += 17000
                    out["items"].append({"name": "Korblox Deathspeaker", "rap": 17000, "type": "Bundle"})
            elif bid == 201 or "headless" in bname.lower():
                if "Headless Horseman" not in found_names:
                    found_names.add("Headless Horseman")
                    out["bundle_value"] += 31000
                    out["items"].append({"name": "Headless Horseman", "rap": 31000, "type": "Bundle"})
            elif "malivinius" in bname.lower():
                if bname not in found_names:
                    found_names.add(bname)
                    out["items"].append({"name": bname, "rap": 0, "type": "Bundle"})

    return out

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        usn = (qs.get("usn") or [""])[0].strip()
        ip = (qs.get("ip") or [""])[0].strip()
        res = get_detail(usn, ip)
        body = json.dumps(res).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
