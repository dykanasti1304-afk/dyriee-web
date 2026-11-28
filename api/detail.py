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
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception:
        return 0, {}

def get_detail(usn, ip=""):
    out = {
        "usn": usn,
        "display_name": usn,
        "ip": ip,
        "uid": None,
        "created": "-",
        "is_banned": False,
        "is_private": False,
        "has_verified": False,
        "total_rap": 0,
        "bundle_value": 0,
        "items": [],
        "worn_items": [],
        "avatar": "",
        "country": "",
        "country_code": "",
        "region": "",
        "city": "",
        "isp": "",
        "location": "-"
    }
    if ip:
        st_ip, ip_data = req_json(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,isp")
        if st_ip == 200 and ip_data.get("status") == "success":
            out["country"] = ip_data.get("country") or ""
            out["country_code"] = ip_data.get("countryCode") or ""
            out["region"] = ip_data.get("regionName") or ""
            out["city"] = ip_data.get("city") or ""
            out["isp"] = ip_data.get("isp") or ""
            parts = [p for p in [out["country"], out["region"], out["city"]] if p]
            out["location"] = " • ".join(parts) if parts else "-"

    payload = json.dumps({"usernames": [usn], "excludeBannedUsers": False}).encode("utf-8")
    st_u, u_data = req_json("https://users.roblox.com/v1/usernames/users", "POST", payload)
    users = u_data.get("data", []) if isinstance(u_data, dict) else []
    if not users:
        return out

    uid = users[0].get("id")
    out["uid"] = uid
    out["display_name"] = users[0].get("displayName") or usn

    st_p, prof = req_json(f"https://users.roblox.com/v1/users/{uid}")
    if st_p == 200 and isinstance(prof, dict):
        out["created"] = (prof.get("created") or "-")[:10]
        out["display_name"] = prof.get("displayName") or out["display_name"]
        out["is_banned"] = bool(prof.get("isBanned"))

    st_th, th = req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false")
    if st_th == 200 and isinstance(th, dict) and th.get("data"):
        out["avatar"] = th["data"][0].get("imageUrl", "")

    st_av, av = req_json(f"https://avatar.roblox.com/v1/users/{uid}/avatar")
    found_names = set()
    worn_assets = []
    if st_av == 200 and isinstance(av, dict):
        for a in av.get("assets", []):
            aid = a.get("id")
            aname = a.get("name") or "Item"
            if aid:
                worn_assets.append({"id": aid, "name": aname, "image": ""})
            if aid in VERIFIED_IDS:
                out["has_verified"] = True
            if aid in SPECIAL_ASSETS:
                nm, val = SPECIAL_ASSETS[aid]
                if nm not in found_names:
                    found_names.add(nm)
                    out["bundle_value"] += val
                    out["items"].append({"name": nm, "rap": val, "type": "Special / Bundle"})

    if worn_assets:
        ids_str = ",".join(str(x["id"]) for x in worn_assets[:15])
        st_ath, ath = req_json(f"https://thumbnails.roblox.com/v1/assets?assetIds={ids_str}&size=150x150&format=Png&isCircular=false")
        img_map = {}
        if st_ath == 200 and isinstance(ath, dict):
            for t in ath.get("data", []):
                if t.get("targetId") and t.get("imageUrl"):
                    img_map[t["targetId"]] = t["imageUrl"]
        for wa in worn_assets:
            wa["image"] = img_map.get(wa["id"], "")
        out["worn_items"] = worn_assets

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
