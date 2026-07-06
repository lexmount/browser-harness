Field-tested on 2026-07-04 (retested 2026-07-06)
CNKI (中国知网, cnki.net) academic literature search — get title/authors/source/year of top papers for a subject query. All extraction is via the cloud browser (new_tab + js); no login required for the brief result list.

## Do this first (direct URL, most reliable)
Navigate straight to the KNS "total library" result page WITH the fixed `crossids` param, then read the grid from the DOM. `korder=SU` means the query is a **主题/Subject** search. The `crossids` value is a stable constant (the total-library database set) — reuse it verbatim.

```python
import urllib.parse
kw = urllib.parse.quote("人工智能")   # your subject term
crossids = "YSTT4HG0,LSTPFY1C,EMRPGLPA,JUP3MUPD,MPMFIG1A,WQ0UVIAA,BLZOG7CK,PWFIRAGL,NLBO1Z6R,NN3FJMUV"
url = f"https://kns.cnki.net/kns8s/defaultresult/index?crossids={urllib.parse.quote(crossids)}&korder=SU&kw={kw}"
new_tab(url); wait_for_load(); wait(5)

# total count (sanity check the grid matches the query)
print(js("document.body.innerText.match(/共找到[\\s\\S]{0,25}/)?.[0]"))

# extract top-N rows
print(js("""
(function(){
  var rows = Array.from(document.querySelectorAll('table.result-table-list tbody tr'));
  return JSON.stringify(rows.slice(0,10).map(function(tr){
    return {
      title:  (tr.querySelector('.name a')||{}).innerText.trim(),
      authors: Array.from(tr.querySelectorAll('.author a')).map(a=>a.innerText.trim()),
      source: (tr.querySelector('.source a, .source')||{}).innerText.trim(),
      date:   (tr.querySelector('.date')||{}).innerText.trim(),        // e.g. "2026-07-06 12:28"
      year:   ((tr.querySelector('.date')||{}).innerText||'').slice(0,4),
      db:     (tr.querySelector('.data')||{}).innerText.trim(),        // 期刊 / 学位论文 / 会议 ...
      link:   (tr.querySelector('.name a')||{}).href                  // kcms2/article/abstract detail page
    };
  }),null,1);
})()
"""))
```

Verified output fields (2026-07-06, kw=人工智能, 460,955 results): title, authors (each 作者 is a separate `<a>` under `.author`), source (期刊名/journal), date+year, db. `.data` gives the database type, `.name a[href]` gives the `kcms2/article/abstract?v=...` detail URL.

## Fallback path: homepage search box
Also verified reliable. Use if the direct URL ever stops populating the grid:
```python
new_tab("https://www.cnki.net"); wait_for_load(); wait(2)
js("document.querySelector('#txt_SearchText').value='人工智能'")   # main search input, id=txt_SearchText
js("document.querySelector('.search-btn').click()")                # 检索 button
wait(6); wait_for_load()
# search opens a NEW tab whose url is .../defaultresult/index?crossids=...&korder=SU&kw=...
tabs = list_tabs()
res = [t for t in tabs if 'defaultresult' in t['url'] and 'kw=' in t['url']]
switch_tab(res[-1]['target_id']); wait(2)
# then run the same extraction js as above
```

## Gotchas
- **STALE-GRID TRAP (important):** navigating to `?korder=SU&kw=<term>` **without** the `crossids` param updates the left-sidebar count correctly (e.g. shows 341,927 for 深度学习) BUT leaves the previous query's rows in the results grid. Always include `crossids` (Do-this-first block) OR use the homepage-search fallback. Sanity-check by comparing the 共找到 count and the row titles against your term.
- **js() targets the focused tab.** After `new_tab`/search-opens-new-tab, explicitly `switch_tab(target_id)` (match on the url) before extracting, or you'll read the wrong tab. `list_tabs()` gives target_id + url.
- **Authors are unseparated in `.author` innerText** ("袁铨许瑞琪刘瑞") — always use `.author a` and map to an array to split them.
- **No usable免登录 JSON API.** The results-grid XHR is `POST https://kns.cnki.net/kns8s/brief/grid` with a `QueryJson` form field, but it is session/format-sensitive and returned `非法逻辑操作符` / `暂无数据` on every hand-crafted payload tried (both `Operate:"="` and `"%="`). Not worth reverse-engineering — the rendered-DOM extraction above is reliable. Use that.
- **No bot challenge on content**, but the page `<title>` shows a horse emoji ("🐴 中国知网"); the DOM and grid load normally regardless — ignore it.
- **http_get (local China IP) not used/needed here** — cnki.net renders and serves the grid fine through the cloud browser; DOM extraction is the path.
- `korder` selects the search field: `SU`=主题/Subject (default from the homepage dropdown). Other CNKI codes exist (TI=题名, AU=作者, KY=关键词) if you need a different field.
