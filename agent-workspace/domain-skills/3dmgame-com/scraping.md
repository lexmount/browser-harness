Field-tested on 2026-07-04 — 3DM Mod站 (mod.3dmgame.com) is a Nuxt SPA; all MOD search/list data comes from one JSON API, `POST /api/search/getModlist`.

## Do this first (fastest, no login, no browser render needed)

The whole "search a game's MODs + find the most-downloaded one" task is one JSON endpoint. It works from BOTH the local China IP (urllib/requests/http_get-style) AND the cloud browser (js fetch) — no anti-bot, no auth, no cookies. The API **ignores all sort params**, so you paginate everything and sort client-side.

Endpoint: `POST https://mod.3dmgame.com/api/search/getModlist`
Body (JSON): `{"search": "<关键词>", "page": <1-based>}`
- Only `search` filters. `keyword`/`name`/`limit` are silently ignored (`limit` does NOT change page size — always 24/page). Sort params (`sort`/`order`/`sortBy`) are ignored too.
- Response: `{success, msg, data:{ mods:[...], count:<fuzzy total>, games:[...] }}`
- `count` is the FUZZY total (title OR game_name matches across many games), so for "艾尔登法环" count=375 but only ~359 are actually game_name=="艾尔登法环".

Per-mod fields (all task fields are in the list — no detail call needed):
- `mods_title` — name
- `mods_download_cnt` — download count (the "下载量" the task asks to rank by)
- `mods_updateTime` — update time (ISO UTC, e.g. `2023-01-05T22:15:50.000Z`; page shows it as Beijing time +8h → 2023年1月5日 14:15:50... note: page label reads 14:15 which is a display quirk, the ISO field is authoritative)
- `mods_desc` — functional intro (for simple tool mods this may just repeat the title)
- `mods_click_cnt` (views), `mods_mark_cnt` (favorites), `id`, `game_name`, `mods_type_name`, `user_nickName`

### Runnable — cloud browser (js fetch), full pagination + client-side max-download

```python
res = js("""
(async () => {
  const kw='艾尔登法环';
  const first = await fetch('/api/search/getModlist',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({search:kw,page:1})}).then(r=>r.json());
  const pages = Math.ceil(first.data.count/24);          // 24 per page, fixed
  const reqs=[]; for(let p=2;p<=pages;p++) reqs.push(
    fetch('/api/search/getModlist',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({search:kw,page:p})}).then(r=>r.json()).then(j=>j.data.mods||[]));
  const rest = await Promise.all(reqs);                  // PARALLEL — sequential 16-page loop TIMES OUT the CDP call
  let all=first.data.mods.slice(); rest.forEach(a=>all=all.concat(a));
  const er = all.filter(m=>m.game_name===kw)             // drop fuzzy cross-game matches
               .sort((a,b)=>b.mods_download_cnt-a.mods_download_cnt);
  const t = er[0];
  return {id:t.id, title:t.mods_title, download:t.mods_download_cnt,
          updateTime:t.mods_updateTime, desc:t.mods_desc, url:'https://mod.3dmgame.com/mod/'+t.id};
})()
""")
print(res)
```
Verified result for 艾尔登法环 (2026-07-04): id **192561**, "艾尔登法环 v1.02-v1.08风灵月影34项修改器", download **104617**, updateTime 2023-01-05T22:15:50Z, url https://mod.3dmgame.com/mod/192561.

### Runnable — local IP fallback (Python urllib, POST). http_get() is GET-only so use urllib for the POST.

```python
import json, urllib.request
def get_page(kw, page):
    req = urllib.request.Request("https://mod.3dmgame.com/api/search/getModlist",
        data=json.dumps({"search":kw,"page":page}).encode(),
        headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

kw="艾尔登法环"; first=get_page(kw,1); import math
pages=math.ceil(first["data"]["count"]/24)
mods=list(first["data"]["mods"])
for p in range(2,pages+1): mods += get_page(kw,p)["data"]["mods"]
er=[m for m in mods if m["game_name"]==kw]
top=max(er, key=lambda m:m["mods_download_cnt"])
print(top["id"], top["mods_title"], top["mods_download_cnt"], top["mods_updateTime"])
```
Confirmed reachable from local China IP (status 200, count 375 identical to cloud). Local and cloud return the same data — no HK-region skew observed on this endpoint.

## Locating the game / UI path (if you must use the page instead of the API)
- Search box on homepage: `input.v-field__input` (placeholder "在这里搜索任何您想要的模组..."). Type + press Enter → navigates to `https://mod.3dmgame.com/mods?search=<urlencoded-kw>`, which fires the same getModlist API.
- MOD detail page: `https://mod.3dmgame.com/mod/<id>`. It server-renders every field into `document.body.innerText` (title, 作者, 更新 time, download count, view count, version, size). Read via `js("document.body.innerText")` — reliable, no extra API needed.

## Gotchas
- **API ignores sorting.** No `sort`/`order`/`sortBy`/`sortType` param works — always paginate all pages and sort by `mods_download_cnt` in your own code.
- **Page size is hard 24.** `limit`/`pageSize` in the body do nothing. Compute pages = ceil(count/24).
- **`count` is fuzzy.** Includes other games whose title contains the keyword. Filter `m.game_name === '<exact game>'` before ranking, or you may pick a mod from the wrong game.
- **Sequential page loop times out the CDP `js()` call.** Fetching ~16 pages one-by-one inside a single `js()` await-loop hit `Runtime.evaluate timed out`. Fix: fire all pages with `Promise.all` (parallel) — one `js()` call then returns fine.
- **Detail API param unknown.** `/api/mods/getModInfo` exists (returns `{"success":false,"msg":"作品不存在或已被删除"}` for id/mods_id GET or POST — wrong param name). Didn't crack it, and didn't need to: the list API already carries title/desc/download/updateTime, and the `/mod/<id>` page renders full detail as text. Use those instead.
- **`mods_desc` can be thin.** For simple tool/trainer mods it just repeats the title. If you need a richer functional writeup, load `/mod/<id>` and read the rendered body text.
- **GET on getModlist = 404.** It is POST-only with a JSON body; a GET (even with `?search=`) returns a Nuxt 404 page.
- No anti-bot / no rate-limit hit during full 16-page parallel pulls on both IPs.

## 主站新闻 / 补丁资讯搜索 (www.3dmgame.com) — 源自 A/site_hints,已 Lexmount 复验 2026-07-07

上面整套是 **mod 站** (mod.3dmgame.com)。**主站** (www.3dmgame.com) 的新闻/补丁/资讯是另一条线,
用主站搜索子域 `so.3dmgame.com`,`type=7` = 新闻搜索。本地 http_get 直连即可,无反爬、无登录、UTF-8。

`https://so.3dmgame.com/?keyword=<url-encoded 关键词>&type=7`

返回 SSR HTML,新闻结果是形如 `https://www.3dmgame.com/news/<YYYYMM>/<id>.html` 的文章链接。

```python
import urllib.request, re, urllib.parse
def _get(url, ref="https://www.3dmgame.com/"):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":ref})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

kw = urllib.parse.quote("赛博朋克2077")
body = _get(f"https://so.3dmgame.com/?keyword={kw}&type=7")
# 每条新闻: <a href="...news/YYYYMM/ID.html">标题</a>(锚文本可能含标签,清一下)
seen, rows = set(), []
for u, inner in re.findall(r'href="(https?://www\.3dmgame\.com/news/\d+/\d+\.html)"[^>]*>(.*?)</a>', body, re.S):
    if u in seen: continue
    seen.add(u)
    title = re.sub(r'<[^>]+>', '', inner).strip()
    if title: rows.append((title, u))
for title, u in rows[:8]:
    print(title, "|", u)
# 实测 2026-07-07 前几条: 《赛博朋克2077》发售六年后 销量突破4000万套 | .../news/202607/3947687.html ...
```

进补丁说明详情页时,文章页正文 `document.body.innerText`(或对正文容器正则)即可拿到版本号/更新内容;
下载链接常在文末,若文章无直链则按 A 的建议报"未观察到直接下载"并给出资源页。

### Gotchas(主站)
- **`type=7` 是新闻搜索**。主站搜索还有其它 type(游戏专区/资源等),新闻类任务用 7。
- 主站搜索返回的是**新闻文章**,不是补丁资源列表本身——补丁下载页要点进文章或游戏专区找。想直接要 MOD
  列表数据仍走上面的 mod 站 `getModlist` API。
- 本地 http_get 通(2026-07-07 主站/搜索子域均从大陆 IP 直取 200),未见反爬。
