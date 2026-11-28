from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request
import concurrent.futures
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

def map_asset_category(type_name):
    t = (type_name or "").lower()
    if "emote" in t:
        return "Emote"
    if "animation" in t:
        return "Animation"
    if "hair" in t:
        return "Hair"
    if any(k in t for k in ["shirt", "tshirt", "jacket", "sweater"]):
        return "Baju"
    if any(k in t for k in ["pants", "shorts", "skirt", "dress"]):
        return "Celana"
    if t in ["head", "torso", "leftarm", "rightarm", "leftleg", "rightleg", "dynamichead"] or any(k in t for k in ["eyebrow", "eyelash"]):
        return "Body"
    return "Aksesoris"

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
        "friends_count": 0,
        "followers_count": 0,
        "followings_count": 0,
        "items": [],
        "worn_items": [],
        "groups": [],
        "favorite_games": [],
        "badges": [],
        "avatar": "",
        "country": "",
        "country_code": "",
        "region": "",
        "city": "",
        "isp": "",
        "location": "-"
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        fut_ip = ex.submit(req_json, f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,isp") if ip else None
        payload = json.dumps({"usernames": [usn], "excludeBannedUsers": False}).encode("utf-8")
        fut_user = ex.submit(req_json, "https://users.roblox.com/v1/usernames/users", "POST", payload)

        if fut_ip:
            st_ip, ip_data = fut_ip.result()
            if st_ip == 200 and ip_data.get("status") == "success":
                out["country"] = ip_data.get("country") or ""
                out["country_code"] = ip_data.get("countryCode") or ""
                out["region"] = ip_data.get("regionName") or ""
                out["city"] = ip_data.get("city") or ""
                out["isp"] = ip_data.get("isp") or ""
                parts = [p for p in [out["country"], out["region"], out["city"]] if p]
                out["location"] = " • ".join(parts) if parts else "-"

        st_u, u_data = fut_user.result()

    users = u_data.get("data", []) if isinstance(u_data, dict) else []
    if not users:
        return out

    uid = users[0].get("id")
    out["uid"] = uid
    out["display_name"] = users[0].get("displayName") or usn

    # Ambil semua data akun secara paralel
    urls = {
        "prof": f"https://users.roblox.com/v1/users/{uid}",
        "headshot": f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=150x150&format=Png&isCircular=false",
        "avatar": f"https://avatar.roblox.com/v1/users/{uid}/avatar",
        "col": f"https://inventory.roblox.com/v1/users/{uid}/assets/collectibles?limit=100",
        "friends": f"https://friends.roblox.com/v1/users/{uid}/friends/count",
        "followers": f"https://friends.roblox.com/v1/users/{uid}/followers/count",
        "followings": f"https://friends.roblox.com/v1/users/{uid}/followings/count",
        "groups": f"https://groups.roblox.com/v1/users/{uid}/groups/roles",
        "fav_games": f"https://games.roblox.com/v2/users/{uid}/favorite/games?accessFilter=Public&limit=12&sortOrder=Desc",
        "badges": f"https://badges.roblox.com/v1/users/{uid}/badges?limit=15&sortOrder=Desc",
        "v1": f"https://inventory.roblox.com/v1/users/{uid}/items/Asset/{VERIFIED_IDS[0]}",
        "v2": f"https://inventory.roblox.com/v1/users/{uid}/items/Asset/{VERIFIED_IDS[1]}",
    }

    res_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {k: ex.submit(req_json, u) for k, u in urls.items()}
        for k, fut in futs.items():
            res_map[k] = fut.result()

    st_p, prof = res_map["prof"]
    if st_p == 200 and isinstance(prof, dict):
        out["created"] = (prof.get("created") or "-")[:10]
        out["display_name"] = prof.get("displayName") or out["display_name"]
        out["is_banned"] = bool(prof.get("isBanned"))

    st_th, th = res_map["headshot"]
    if st_th == 200 and isinstance(th, dict) and th.get("data"):
        out["avatar"] = th["data"][0].get("imageUrl", "")

    for skey, okey in [("friends", "friends_count"), ("followers", "followers_count"), ("followings", "followings_count")]:
        st_s, sdata = res_map[skey]
        if st_s == 200 and isinstance(sdata, dict):
            out[okey] = int(sdata.get("count") or 0)

    # Avatar assets (Body, Hair, Baju, Celana, Aksesoris, Animation) + Emotes
    st_av, av = res_map["avatar"]
    found_names = set()
    worn_assets = []
    seen_worn_ids = set()
    if st_av == 200 and isinstance(av, dict):
        for a in av.get("assets", []):
            aid = a.get("id")
            aname = a.get("name") or "Item"
            atype = (a.get("assetType") or {}).get("name") or ""
            cat = map_asset_category(atype)
            if aid and aid not in seen_worn_ids:
                seen_worn_ids.add(aid)
                worn_assets.append({"id": aid, "name": aname, "category": cat, "image": ""})
            if aid in VERIFIED_IDS:
                out["has_verified"] = True
            if aid in SPECIAL_ASSETS:
                nm, val = SPECIAL_ASSETS[aid]
                if nm not in found_names:
                    found_names.add(nm)
                    out["bundle_value"] += val
                    out["items"].append({"name": nm, "rap": val, "type": "Special / Bundle"})

        for em in av.get("emotes", []):
            eid = em.get("assetId")
            ename = em.get("assetName") or "Emote"
            if eid and eid not in seen_worn_ids:
                seen_worn_ids.add(eid)
                worn_assets.append({"id": eid, "name": ename, "category": "Emote", "image": ""})

    if not out["has_verified"]:
        for vk in ["v1", "v2"]:
            st_v, vd = res_map[vk]
            if st_v == 200 and isinstance(vd, dict) and len(vd.get("data", [])) > 0:
                out["has_verified"] = True
                break

    st_col, col = res_map["col"]
    if st_col == 403:
        out["is_private"] = True
    elif st_col == 200 and isinstance(col, dict):
        for it in col.get("data", []):
            nm = it.get("name") or "Limited Item"
            rap = int(it.get("recentAveragePrice") or 0)
            out["total_rap"] += rap
            out["items"].append({"name": nm, "rap": rap, "type": "Limited"})

    # Groups
    st_g, gdata = res_map["groups"]
    groups_list = []
    if st_g == 200 and isinstance(gdata, dict):
        for entry in gdata.get("data", [])[:20]:
            grp = entry.get("group") or {}
            role = entry.get("role") or {}
            if grp.get("id"):
                groups_list.append({
                    "id": grp.get("id"),
                    "name": grp.get("name") or "Group",
                    "members": int(grp.get("memberCount") or 0),
                    "role": role.get("name") or "Member",
                    "image": ""
                })

    # Favorite Games
    st_fg, fgdata = res_map["fav_games"]
    games_list = []
    if st_fg == 200 and isinstance(fgdata, dict):
        for gm in fgdata.get("data", [])[:12]:
            if gm.get("id"):
                games_list.append({
                    "id": gm.get("id"),
                    "name": gm.get("name") or "Game",
                    "visits": int(gm.get("placeVisits") or 0),
                    "image": ""
                })

    # Badges
    st_bg, bgdata = res_map["badges"]
    badges_list = []
    if st_bg == 200 and isinstance(bgdata, dict):
        for bd in bgdata.get("data", [])[:15]:
            if bd.get("id"):
                badges_list.append({
                    "id": bd.get("id"),
                    "name": bd.get("name") or "Badge",
                    "image": ""
                })

    # Ambil semua thumbnail (Assets+Emote, Group, Game, Badge) secara paralel
    thumb_urls = {}
    if worn_assets:
        a_ids = ",".join(str(x["id"]) for x in worn_assets[:60])
        thumb_urls["assets"] = f"https://thumbnails.roblox.com/v1/assets?assetIds={a_ids}&size=150x150&format=Png&isCircular=false"
    if groups_list:
        g_ids = ",".join(str(x["id"]) for x in groups_list)
        thumb_urls["groups"] = f"https://thumbnails.roblox.com/v1/groups/icons?groupIds={g_ids}&size=150x150&format=Png&isCircular=false"
    if games_list:
        u_ids = ",".join(str(x["id"]) for x in games_list)
        thumb_urls["games"] = f"https://thumbnails.roblox.com/v1/games/icons?universeIds={u_ids}&size=150x150&format=Png&isCircular=false"
    if badges_list:
        b_ids = ",".join(str(x["id"]) for x in badges_list)
        thumb_urls["badges"] = f"https://thumbnails.roblox.com/v1/badges/icons?badgeIds={b_ids}&size=150x150&format=Png"

    if thumb_urls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            tfuts = {k: ex.submit(req_json, u) for k, u in thumb_urls.items()}
            for k, fut in tfuts.items():
                st_t, tdata = fut.result()
                tmap = {}
                if st_t == 200 and isinstance(tdata, dict):
                    for item in tdata.get("data", []):
                        if item.get("targetId") and item.get("imageUrl"):
                            tmap[item["targetId"]] = item["imageUrl"]
                if k == "assets":
                    for wa in worn_assets:
                        wa["image"] = tmap.get(wa["id"], "")
                elif k == "groups":
                    for gr in groups_list:
                        gr["image"] = tmap.get(gr["id"], "")
                elif k == "games":
                    for gm in games_list:
                        gm["image"] = tmap.get(gm["id"], "")
                elif k == "badges":
                    for bd in badges_list:
                        bd["image"] = tmap.get(bd["id"], "")

    out["worn_items"] = worn_assets
    out["groups"] = groups_list
    out["favorite_games"] = games_list
    out["badges"] = badges_list
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
