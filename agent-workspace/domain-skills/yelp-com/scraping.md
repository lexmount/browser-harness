Field-tested on 2026-07-04
Yelp = business reviews (restaurants, ratings, review counts). Direct scraping is BLOCKED by DataDome on every path we control; the working fallback is reading restaurant names off a Bing SERP in the cloud browser, and the only clean rating/review data comes from the key-gated Yelp Fusion API.

## Do this first
Do NOT try to load yelp.com directly — it will fail (see Gotchas). Get the restaurant list via a Bing search in the cloud browser, then read the `li.b_algo` result text. This reliably returns the top restaurant NAMES for a "best X near Y" query.

```python
# CLOUD BROWSER (new_tab/js). Bing is reachable from the HK cloud egress; Yelp is not.
new_tab("https://www.bing.com/search?q=best+italian+restaurants+near+Times+Square+yelp")
wait_for_load(20); wait(3)
import json
res = js("""
Array.from(document.querySelectorAll('li.b_algo')).map(li=>({
  title:(li.querySelector('h2')||{}).innerText||'',
  cite:(li.querySelector('cite')||{}).innerText||'',
  text:(li.innerText||'').replace(/\\n+/g,' | ').slice(0,300)
})).filter(r=>/yelp/i.test(r.cite)||/yelp/i.test(r.title)||/yelp/i.test(r.text))
""")
print(json.dumps(res, ensure_ascii=False, indent=1))
# VERIFIED output: Yelp's own SERP snippet lists the ranked names, e.g.
# "Top 10 Best Italian ... - Yelp - Serafina Times Square, Trattoria Trecolori,
#  Carmine's - Time Square, Tony's Di Napoli, Gatsby's Landing Times ..."
# -> parse the "- Yelp - A, B, C, ..." tail of the snippet for the ranked top list.
```

For a per-restaurant review count, a targeted Bing query sometimes surfaces one (not a clean star rating):
```python
new_tab("https://www.bing.com/search?q=Carmine%27s+Times+Square+yelp+rating+reviews")
wait_for_load(20); wait(3)
txt = js("document.body?document.body.innerText:''")
# VERIFIED to yield a line like "Reviews: 694K" — coarse, and star rating is usually absent.
```

## Clean structured data: Yelp Fusion API (needs an API key)
`api.yelp.com/v3` is NOT DataDome-blocked (it answers from `envoy`, not DataDome). It just requires auth. If you have a Yelp API key, this is the only path that returns real rating + review_count fields:
```python
# LOCAL http_get is fine here (api.yelp.com is reachable, not IP-blocked).
h={"Authorization":"Bearer <YELP_API_KEY>"}
r = http_get("https://api.yelp.com/v3/businesses/search?location=Times+Square,NY&term=italian&sort_by=rating&limit=3", headers=h)
# Response JSON: businesses[].name, .rating, .review_count, .location, .url
```
VERIFIED without a key: returns HTTP 400 `{"error":{"code":"VALIDATION_ERROR","description":"Authorization is a required parameter."}}` — confirms the endpoint is live and only auth-gated, not blocked.

## Gotchas
- **Yelp is fully behind DataDome (Server: DataDome, X-DataDome: protected).** Both egress IPs are blocked:
  - Local http_get (China IP): `HTTP 403 Forbidden`, DataDome captcha HTML body ("Please enable JS and disable any ad blocker", loads `ct.captcha-delivery.com/c.js`).
  - Cloud browser new_tab (Hong Kong IP, `X-Served-By: cache-hkg...-HKG`): navigation fails at the network layer → page is `chrome-error://chromewebdata/` with title "Access to www.yelp.com was denied / HTTP ERROR 403". Because the navigation itself fails, DataDome's JS challenge never even runs — waiting 30s+ does NOT clear it. This is a hard block, not a solvable challenge.
  - Affected hosts (all 403/DataDome): `www.yelp.com`, `m.yelp.com`, `www.yelp.com/search/snippet` (the internal JSON search endpoint), `www.yelp.ca`.
- **jina.ai reader (`r.jina.ai/<url>`) does NOT bypass it** — returns "This page maybe requiring CAPTCHA". (Also: `r.jina.ai` connection-resets from the local China IP; only reachable via the cloud browser, where it still hits the captcha.)
- **Bing link hrefs are useless** — every `li.b_algo` result wraps its href in Bing click-tracking, so `a.href` never contains `yelp.com`. The yelp.com URL is only present as visible text in `cite`/innerText. Extract from `.innerText`, not from `href`.
- **`site:yelp.com` Bing queries returned an empty/interstitial page** (innerText ~105 chars). Use a natural-language query ("best italian restaurants near Times Square yelp") instead — that reliably returns the Yelp rich snippet with the ranked name list.
- **Bing SERP gives names, not ratings.** It's enough to identify the top-3 restaurants by name/rank, but per-restaurant star rating + review_count are not consistently present. For those exact fields you need the Fusion API key. If the task only needs "top 3 restaurants", the Bing path alone suffices.
- Cloud egress is Hong Kong, so Bing may return region-tinted results; the Yelp snippet content itself is US (Times Square) as queried.
