# SenseCraft HMI (Seeedash) Layout JSON — Reference

Reverse-engineered from 518 public templates (`/api/v2/template/detail/{id}`), 309 of them for the reTerminal E1002. This is the same object the Canvas editor's **Export** writes and **Import** reads, and what `page/detail` returns in its `data` string.

## 1. Top-level document

```json
{
  "dither": 3,
  "stageSize": { "width": 1872, "height": 953 },
  "stageElements": [ { ...__device_container_group__ } ]
}
```

| Key | Meaning |
|---|---|
| `dither` | Color-quantization mode for the target panel. **E1002 = 3** (309/309 templates). E1001 mono = 0 (sometimes 4), E1003 = 5, E1004 = 3. |
| `stageSize` | The editor viewport size at save time. Irrelevant to the device; any value works. |
| `stageElements` | Array. Element 0 is always the device container group. Anything else at top level is off-canvas scratch and is not rendered. |

## 2. The device container

```json
{
  "id": "__device_container_group__",
  "type": "group",
  "x": 42.5, "y": 246.8,
  "width": 800, "height": 480,
  "canvasRotation": 0,
  "children": [ ...all visible elements... ]
}
```

- `width`/`height` = panel resolution (**800×480** for E1002).
- `x`/`y` are where the container sits in the editor; children use coordinates **relative to the container**, so (0,0) is the panel's top-left.
- Children are drawn in array order (first = bottom, last = top). Put background rectangles first.
- Every child normally carries `"parentId": "__device_container_group__"` (or its enclosing group's id).

## 3. Keys common to all elements

| Key | Type | Notes |
|---|---|---|
| `id` | string | Convention: `"{type}-{unix_ms}"`, e.g. `text-1764925180547`. Any unique string works. |
| `type` | string | One of the types in §4. |
| `x`, `y`, `width`, `height` | number | Pixels, relative to parent. Decimals fine. |
| `rotation` | number | Degrees. Usually 0. |
| `parentId` | string | Enclosing group's id. |

Optional styling on most shapes/groups: `fill`, `stroke` (hex or `"transparent"`), `strokeWidth` (default 0), `cornerRadius`, `shadowEnabled/shadowColor/shadowBlur/shadowOffsetX/shadowOffsetY/shadowOpacity`.

### Text styling keys (shared by `text`, `date`, `countdown`, `data`)

| Key | Values |
|---|---|
| `value` | The string shown (for dynamic types, a placeholder/preview) |
| `color` | Hex text color |
| `fontFamily` | `Montserrat` (default, 90% of uses), `Roboto`, `Digital Numbers`, `Carter One`, `Source Han Sans CN`, `serif`, `sans-serif`, plus a few Google fonts |
| `fontSize` | Number (px) |
| `fontStyle` | `normal`, `bold`, `italic`, `italic bold` |
| `fontWeight` | Optional; `400`, `700`, or `"700"` — `fontStyle: "bold"` is the more common route |
| `textAlign` | `left`, `center`, `right` |
| `verticalAlign` | `top`, `middle`, `bottom` (optional) |
| `widthMode` | `fixed` (wrap inside `width`) or `auto` (grow to fit) |
| `lockHeight` | boolean |
| `lineHeight` | number, e.g. `1.2` |
| `letterSpacing` | number |
| `textDecoration` | e.g. `underline` |

## 4. Element types

### `rectangle`
```json
{"type":"rectangle","id":"rectangle-1","x":0,"y":0,"width":800,"height":480,
 "fill":"#ffffff","stroke":"#000000","strokeWidth":0,"cornerRadius":0,"rotation":0,
 "parentId":"__device_container_group__"}
```
Optional `gradient`, `fillOpacity`. (There is no separate rounded-rect type; use `cornerRadius`.)

### `circle` — `x,y,width,height` box; optional `radius`.
### `ellipse` — adds `radiusX`, `radiusY`.
### `polygon` — adds `sides` (int), `radius`.
### `triangle` — `points: [x1,y1,x2,y2,x3,y3,x1,y1]` relative to element.
### `line`
```json
{"type":"line","points":[0,0,283,0],"stroke":"#000000","strokeWidth":3,"x":250,"y":102,"width":283,"height":1,"dash":[6,4]}
```
### `drawing` — freehand: `points: [x,y,x,y,...]`, `stroke`, `strokeWidth`, `tool: "brush"`.

### `text`
```json
{"type":"text","id":"text-1","value":"Hello","x":40,"y":40,"width":300,"height":40,
 "color":"#000000","fontFamily":"Montserrat","fontSize":30,"fontStyle":"bold",
 "textAlign":"left","widthMode":"fixed","rotation":0,"parentId":"__device_container_group__"}
```

### `image`
`src` is either an `https://` URL (Seeed rehosts uploads under `sensecraft-hmi-api.seeed.cc/oss/images/…`) or a `data:image/png;base64,…` URI. Optional `invertColors`, `cornerRadius`, `opacity`.

### `group`
Same box keys plus `children[]`. Two layout modes:
- absolute (default): `"layout": {"type":"absolute","gap":0,"padding":0}` or no `layout` key; children positioned with their own x/y relative to the group.
- flex: `"layout": {"type":"flex","direction":"row","gap":2,"padding":0,"alignItems":"center","justifyContent":"start"}` — children auto-flowed.
Groups can have `fill`/`stroke`/`cornerRadius` (acts as a card background).

### `date` — live clock / date (no API needed)
```json
{"type":"date","id":"time-1","value":"13:11","x":100,"y":80,"width":300,"height":100,
 "dataTransform":{"type":"time","options":{"format":"h:mm A","timezone":"America/New_York"}},
 "color":"#000000","fontFamily":"Montserrat","fontSize":90,"fontStyle":"bold","textAlign":"center"}
```
`dataTransform.type` is `time` or `date`. Formats seen (Day.js-style tokens):
- time: `HH:mm` (24h), `h:mm A` / `hh:mm A` (12h), `HH:mm:ss`, `H:mm`
- date: `MM/DD/YYYY`, `MM/DD`, `DD`, `DDD` (short weekday, e.g. "Wed"), `DDDD` (full weekday), `MMM`, `YYYY`, `YYYY.MM.DD`, `DD.MM.YYYY`, `ddd DD MMM YYYY`
- `timezone`: IANA name (`America/New_York` — follows DST) **or** fixed offset (`UTC-4`). Prefer IANA.
- Some date widgets also carry `implicitTimezone` / `implicitUtcOffsetSeconds` — editor bookkeeping, optional.

### `countdown`
```json
{"type":"countdown","value":"2026-12-25 00:00:00",
 "dataTransform":{"type":"countdown","options":{"format":"{d}","timezone":"America/New_York"}}, ...text styling}
```
`value` is the target datetime; `{d}` renders days remaining.

### `clock` — analog / flip clock widget
```json
{"type":"clock","width":400,"height":400,
 "clockConfig":{"clockStyle":"analog"|"flip","hourFormat":"24"|"12","showSecond":true,
   "timezone":"America/New_York","faceColor":"#ffffff","borderColor":"#000000",
   "hourColor":"#000000","minuteColor":"#000000","secondColor":"#ff0000"}}
```

### `calendar`
```json
{"type":"calendar","calendarConfig":{
  "calendarType":"google-calendar-month" | "google-calendar-week" | "google-calendar-week-day",
  "year":2026,"month":8,
  "tableConfig":{"title":"September 2026","titleStyle":{...},
    "dataSource":{"type":"direct","data":[[null,null,1,2,3,4,5],[6,...]]},
    "renderConfig":{"columns":7,"rows":5,"cellWidth":42.5,"cellHeight":29.6,"cellGap":2,
      "columnHeaders":["Sun","Mon","Tue","Wed","Thu","Fri","Sat"],"showColumnHeader":true,
      "cellStyle":{...},"columnHeaderStyle":{...},"rowHeaderStyle":{"fontSize":12}}},
  "todayStyle":{"fill":"#000000","color":"#ffffff","borderColor":"#000000","fontSize":16}}}
```
`month` is **0-based**. The editor regenerates the grid; safest to let it (add via UI once, then copy).

### `data` — the universal API widget
```json
{"type":"data","id":"data-1","label":"Current Weather - Temperature (°F)",
 "requiredPlatform":"weather",
 "dataUrl":"https://sensecraft-hmi-api.seeed.cc/proxy/weather?latitude=38.9097&longitude=-77.0434&forecast_days=7&timeformat=unixtime&current=temperature_2m%2Cweather_code%2Crelative_humidity_2m&daily=weather_code%2Ctemperature_2m_max%2Ctemperature_2m_min",
 "dataHeaders":{},
 "dataKey":"current.temperature_2m",
 "dataTransform":{"type":"custom","options":{"customFunction":"return Math.round(value*9/5+32) + '°';"}},
 "temperatureUnit":"celsius",
 "value":"72°",
 "sanitizedFields":["dataHeaders.api-key"],
 ...text styling, x/y/width/height}
```
- `dataUrl` — any public JSON endpoint. `dataKey` — dot path, numeric index for arrays (`daily.temperature_2m_max.0`).
- `dataHeaders` — request headers. **Weather widgets need an `api-key` header that Seeed issues per account**; public templates ship it masked (`sk_7***QyQl`). Leave `dataHeaders: {}` and, after import, click the widget → the editor re-attaches your key. Same for `X-CMC_PRO_API_KEY`, `Authorization`, `apikey=`.
- `requiredPlatform` — tells the editor which key to inject: `weather`, `device`, `stock` (Twelve Data), `coinmarketcap`, `youtube`, `github`, `zenquotes`, `hackernews`, `todoist`, `externalApi` (generic, no key).
- `value` — preview text shown in the editor.
- `dataTransform.type` options:

| type | options | effect |
|---|---|---|
| *(omitted)* | | raw value |
| `number` | `precision`, `thousandsSeparator: "comma"` | fixed decimals |
| `compactNumber` | `precision`, `unitSystem: "western"` | 12.3K style |
| `currency` | `precision`, `currencyUnit`, `symbolPosition: "prefix"`, `thousandsSeparator` | $1,234.56 |
| `percentage` | `precision`, `percentagePosition: "suffix"` | 12% |
| `time` / `date` | `format`, `timezone` | format a unix timestamp from the API (e.g. `daily.sunrise.0`) |
| `custom` | `customFunction` | JS body with `value` in scope, must `return` a string |
| `weatherIcon` | plus `"outputType":"image"` on dataTransform | renders WMO `weather_code` as an icon (no text keys needed) |
| `imageUrl` | plus `"outputType":"image"` | fetches the URL in the field and shows it as an image |

**Weather proxy** (`/proxy/weather` is Open-Meteo behind Seeed's key). Query params: `latitude`, `longitude`, `timezone` (URL-encoded IANA), `timeformat=unixtime`, `forecast_days`, `current=…`, `daily=…`. Useful keys: `current.temperature_2m`, `current.apparent_temperature`, `current.relative_humidity_2m`, `current.weather_code`, `current.wind_speed_10m`, `current.rain`, `daily.temperature_2m_max.N`, `daily.temperature_2m_min.N`, `daily.weather_code.N`, `daily.time.N`, `daily.sunrise.N`, `daily.sunset.N`, `daily.precipitation_sum.N`. Values are °C — convert with a `custom` transform or `temperature_unit=fahrenheit` in the URL.

**Device sensors** (`requiredPlatform: "device"`): `dataUrl: https://sensecraft-hmi-api.seeed.cc/api/v1/user/device/iot_data/{DEVICE_ID}` with `dataKey` = `result.battery.level`, `result.sensor.temp`, `result.sensor.humidity`. Your E1002's id is **20233536**.

### `chart` — ECharts
```json
{"type":"chart","chartConfig":{
  "dataSource":{"type":"api","dataUrl":"…proxy/weather?…&daily=temperature_2m_max","xAxisDataKey":"daily.time","yAxisDataKey":"daily.temperature_2m_max"},
  "option":{"type":"line"|"bar"|"gauge"|"candlestick", ...standard ECharts option (series, xAxis, yAxis, grid, title)}}}
```
`dataSource.type: "direct"` with `data:[{"value":75}]` for static. For gauge, `series[0].min/max` and `detail.formatter`.

### `list`
```json
{"type":"list","listConfig":{
  "dataSource":{"type":"api","dataUrl":"https://api.todoist.com/api/v1/tasks","dataHeaders":{"Authorization":"Bearer …"},"dataKey":""},
  "showTitle":true,"title":"To-Do","titleStyle":{"fontSize":18,"fontWeight":"700","color":"#000000","textAlign":"left","fontFamily":"Montserrat"},
  "renderConfig":{"itemHeight":30,"itemWidth":280,"itemGap":6,
    "icon":{"enabled":true,"type":"checkbox","dataKey":"is_completed","width":20,"height":20},
    "primaryText":{"fields":[{"dataKey":"content"}],"style":{"fontSize":17,"color":"#3D3D3D","textAlign":"left","fontWeight":"normal"}},
    "itemLayout":{"gap":8,"padding":0,"contentGap":4}}}}
```
`dataKey` points at the array in the response (`""` = root array). Reddit/RSS-type feeds go through this or the `rss` widget.

### `rss`
```json
{"type":"rss","rssConfig":{"url":"https://www.reddit.com/r/Showerthoughts/hot/.rss","items":4,"showDate":false,"showDescription":true},
 "fill":"transparent","stroke":"transparent","strokeWidth":0,"cornerRadius":0, x/y/width/height}
```

### `html`
```json
{"type":"html","htmlConfig":{"htmlUrl":"https://…","htmlRenderMode":"iframe"|"preview","previewWidth":400,"previewHeight":300}, box+fill/stroke}
```
Renders a screenshot of a public URL on the device.

### `qrcode` / `barcode`
`value` = encoded string, `src` = the editor-generated SVG (regenerated on edit; can be omitted on import and re-set by clicking the widget). Barcode adds `barcodeFormat: "CODE128"`.

## 5. E1002 color rules

The panel is 6-color ACeP (Spectra 6). Templates almost exclusively use the six pure values:

`#000000` black · `#ffffff` white · `#ff0000` red · `#ffff00` yellow · `#0000ff` blue · `#00ff00` green

Anything else is dithered (`dither: 3`), which looks noisy on flat areas. Greys like `#666666` are common for secondary text and dither acceptably at small sizes; avoid gradients and photos unless you want the dither look. `#rrggbbaa` with `00` alpha = transparent.

## 6. Practical import workflow

1. Build the JSON (dither 3, 800×480 container, children in z-order).
2. Workspace → your design → Import (inward arrow) → select file. This **replaces** the canvas.
3. Click each `data` widget once so the editor injects your weather/device keys (`sanitizedFields` tells it which).
4. Preview → Save → Apply/Deploy.

## 7. Corpus stats (for calibration)

Elements across 518 layouts: data 3725 · text 2418 · rectangle 1596 · group 1464 · image 1352 · date 688 · line 318 · circle 152 · countdown 127 · drawing 86 · clock 60 · calendar 51 · chart 42 · list 30 · html 25 · triangle 19 · polygon 8 · ellipse 6 · qrcode 6 · rss 5 · barcode 2.
Data platforms: weather 2279 · externalApi 219 · device 135 · coinmarketcap 124 · zenquotes 73 · stock 52 · youtube 34 · github 25 · hackernews 15 · todoist 1.

---

## 8. How the renderer actually behaves (verified on the live editor, Sep 2026)

Everything above was inferred from exported templates. This section is what we learned by
importing `board/layout.json` into the real editor and comparing the device **Preview** against
the feed. Read it before designing any new board; every point cost a round-trip.

### 8.1 `data` widget pipeline

For each `data` widget the renderer does, in order:

1. Fetch `dataUrl` (server-side, from Seeed's cloud — the URL must be public).
2. Resolve `dataKey` (dot path, numeric array index) against the JSON.
3. **If the resolved value is `null`/missing, substitute the widget's own `value` (the preview
   text).** An empty preview is then coerced to `0`. So the preview text is not cosmetic: it is
   the fallback input. For any field that can be null, set `"value": "N/A"` and make the
   transform treat `"N/A"` as missing.
4. Apply `dataTransform`. For `custom`, the JS body runs with `value` in scope (plus
   `formatDate` and `Math`, per the editor's hint) and must return a string.
5. **If the result is the empty string `''`, the renderer draws the literal text `N/A`.** A
   widget that should draw nothing must return a zero-width space `'​'` instead.
6. **A result that is a bare number (`"17"`) is re-formatted (`17.0`).** Append `'​'` to
   numeric-looking strings to keep them as-is.

The editor canvas (not Preview) runs the same pipeline on the baked preview `value` until a
widget has fetched once; clicking a widget triggers its first fetch. Preview always fetches
live and is what the device will show.

### 8.2 Colour cannot be data-driven — use stacked widgets

`color` is fixed per widget. To colour a word by state, stack several `data` widgets in the
same box, one per colour, each bound to the same `dataKey`, each returning its text only when
its condition holds and `'​'` otherwise. The board uses this for the state word
(green working / blue idle+done / red blocked+error+stale) and for the `updated` time (black
when fresh, red `STALE · …` when older than 45 min).

### 8.3 Progress bars

Rectangles cannot be resized from data. A text bar works: return
`'█'.repeat(k) + '░'.repeat(n - k)`. Montserrat lacks both glyphs; the renderer's fallback font
draws `█` solid and `░` as a fine hatch, which reads well on the panel. Keep it to ~10 cells at
15 px and give the widget a fixed width so it cannot wrap.

### 8.4 Time formatting

`Date`, `toLocaleTimeString` and the `timeZone` option all work in custom functions
(`new Date(unix*1000).toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit',
timeZone:'America/New_York'})`). The built-in `dataTransform.type: "time"` also works but
cannot be combined with a condition, which is why the stale/fresh pair uses custom functions.

### 8.5 Device (battery/temperature/humidity) widgets do NOT survive import

`requiredPlatform: "device"` widgets need the account's device api-key. The editor injects it
into widgets it creates itself, but **not into imported ones**: tried `dataHeaders: {}`, a
placeholder mask `sk_***`, and the exact mask string copied from an Export
(`sk_i***fT1W` format) with `sanitizedFields: ["dataHeaders.api-key"]` — all render `N/A`.
Ship a placeholder text and add the widget by hand after import:
**Data → Device → Load Sensor Data → Battery Level → Confirm.** The widget Seeed generates
looks like this (from an Export; the key is masked in exports and in this doc):

```json
{"type":"data","requiredPlatform":"device","label":"Battery Level",
 "dataUrl":"https://sensecraft-hmi-api.seeed.cc/api/v1/user/device/iot_data/20233536",
 "dataHeaders":{"api-key":"sk_****"},"sanitizedFields":["dataHeaders.api-key"],
 "dataKey":"result.battery.level","value":"11",
 "dataTransform":{"type":"percentage","options":{"precision":0}},
 "fontSize":16,"color":"#ffffff","fontFamily":"Montserrat","fontStyle":"normal","textAlign":"center"}
```

The Device dialog also exposes `result.sensor.temp` (°C) and `result.sensor.humidity` (%).
Values are from the device's last check-in, not live.

### 8.6 Export / Import / buttons

* **Import** (inward arrow, Workspace) replaces the whole canvas. **Export** (outward arrow)
  writes this same JSON, with api-keys masked. Exports are gitignored here (`dashboard_*.json`).
* **Save** stores the design. **Apply** renders it and pushes the bitmap to the device.
  **Publish** shares the design as a public template — never use it for a board that embeds a
  private feed URL or device id.
* Data widgets in the corpus stats above are 3725 of 11 k elements; a board with ~30 of them
  imports and previews fine.

### 8.7 Recipe: a feed-driven text widget

```json
{"type":"data","id":"data-1","x":30,"y":100,"width":218,"height":26,
 "requiredPlatform":"externalApi",
 "dataUrl":"https://<user>.github.io/<repo>/status.json",
 "dataHeaders":{},"sanitizedFields":[],
 "dataKey":"agents.0.state",
 "value":"N/A",
 "dataTransform":{"type":"custom","options":{"customFunction":
   "var v=(value==null||value===''||value==='N/A')?null:value;var B='\\u200b';var s=String(v==null?'':v).toLowerCase();return ['working'].indexOf(s)>=0?s.toUpperCase():B;"}},
 "color":"#00ff00","fontFamily":"Montserrat","fontSize":18,"fontStyle":"bold","textAlign":"left",
 "widthMode":"fixed","lockHeight":true,"rotation":0,"parentId":"__device_container_group__"}
```

`board/build_layout.py` generates all of these; start there for a new board rather than by hand.

---

## 9. Troubleshooting: the display never refreshes by itself (solved Sep 17, 2026)

**Symptom.** Page deployed fine, Interval(min)=15, but the E1002 only redrew when the green
button was pressed. Overnight on battery and for hours on USB power it never woke itself. The
Device page said "Online" the whole time and the battery read 11 % then 0 %.

**Cause.** Stock firmware **v1.0.7** (Dec 2025). Fixed by flashing **v1.2.2** (released
2026-09-10), whose release notes read: "more reliable screen refreshes, consistent update
schedules, and reduced battery drain caused by refresh issues … Automatic refresh schedules
now stay on track after the daily 4:30 AM screen maintenance … Fixed the issue where saved
content failed to refresh after wake-up despite Wi-Fi being connected."
(https://sensecraft-hmi-docs.seeed.cc/en/release-notes/). After the flash the device log showed
`Refresh timer started, interval=900s` and `battery_pct=100.00 charging=1`; the old 0 % was a
bad reading, not a dead battery.

**Proof.** A render probe (below) logged unattended renders at +15.7 min and +15.7 min after
Apply. Each cycle is the interval plus ~40 s of wake + 6-colour redraw, so the schedule drifts
about a minute later per cycle.

**How to flash.** The Device page "Update" button opens the USB flasher
(`sensecraft.seeed.cc/hmi/tools/firmware`). It needs **Chrome or Edge** (Safari has no Web
Serial), the display connected **directly to the computer with a data-capable USB-C cable**,
the back **power switch ON**, and the device **awake** (press green once). The E1002 uses a
CH340 (USB vendor 0x1A86, product 0x7523); macOS has a built-in driver and the port appears as
`/dev/cu.usbserial-*`. If the Mac lists no USB device at all, it is the cable or the switch,
not a driver. Leave **Full Flash OFF** to keep Wi-Fi and deployed designs.

**Things that were NOT the cause** (all checked): the Interval setting, a single-page
pagelist (documented as supported), Battery Saver either way, the feed, the layout, Wi-Fi.
"Online" on the Device page is not evidence that the device is waking.

**Settings semantics** (from Seeed's older docs, still in the docs repo history):
Interval = how often the device wakes to pull new data, and also the page-rotation period when
the pagelist has several pages. Battery Saver ON = deep sleep with a timer wake each interval;
OFF = always on. A sleeping device only learns about a new design or setting at its next wake;
press the green button to apply immediately. Green button: single press = refresh (one beep),
5 s hold = clear the screen.

**Render probe.** `python3 board/build_layout.py --probe https://webhook.site/<token>` writes a
gitignored `board/layout.probe.json` whose "rendered" footer widget fetches a request logger
instead of the feed. Every cloud render then leaves a timestamped hit you can read from
`https://webhook.site/token/<token>/requests`. Renders only happen when the device asks, so the
hit log is a wake log. Free webhook.site tokens stop after 100 requests (~1 day at 15 min) and
expire in 7 days, so re-import the normal `layout.json` when done. The normal layout keeps the
"rendered h:mm" stamp (bound to the feed), so picture age is always visible next to data age.

**Status icons.** v1.2.2 draws its own icons in the top-right corner over the page. A battery
with a slash was seen while on USB at 100 %; Seeed does not document it. The wiki documents
only a low-battery icon below 20 %. The gauge is a voltage divider on an ADC, not a fuel gauge,
so its readings jump when USB is connected or removed.
