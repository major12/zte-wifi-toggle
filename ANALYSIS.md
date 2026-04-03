# ZTE Hotspot Web UI — Reverse Engineering Analysis

A post-mortem of automating the ZTE MF935 / F30 Pro Wi-Fi toggle via CLI,
covering every technical fact needed, what went wrong, and how to succeed in
one attempt next time.

---

## Part 1 — Technical Reference

### 1.1 Device and Endpoint

| Property | Value |
|---|---|
| Device | ZTE MF935 (also branded F30 Pro) |
| Admin URL | `http://192.168.0.1/index.html` |
| GET API | `GET /goform/goform_get_cmd_process?cmd=FIELD1,FIELD2&multi_data=1` |
| POST API | `POST /goform/goform_set_cmd_process` |
| UI type | Single-Page Application with hash routing (`#login`, `#wifi`, etc.) |

### 1.2 Authentication — Login Flow

The login uses a **double SHA-256** scheme. The device serves a one-time
nonce `LD` that is mixed with the hashed password:

```
login_pw = SHA256_UPPER( SHA256_UPPER(plaintext_password) + LD )
```

`LD` is fetched unauthenticated:
```
GET /goform/goform_get_cmd_process?isTest=false&cmd=LD
→ {"LD": "3EEF437FE5298C29..."}
```

Login POST (no AD required — `service.js` explicitly skips AD for `goformId=LOGIN`):
```
POST /goform/goform_set_cmd_process
Body: goformId=LOGIN&isTest=false&password=<computed_hash>
```

Success response: `{"result":"0"}` plus a `Set-Cookie: stok=<HEX24>` header.

The `stok` cookie must be sent with every subsequent request.

**Source:** `config.js` → `WEB_ATTR_IF_SUPPORT_SHA256: 2`,
`util.js` → `SHA256()` with uppercase flag `r=1`,
`service.js` → `function a4()` (login handler).

### 1.3 SHA-256 Implementation Detail

The device ships its own SHA-256 in `util.js`. The critical difference from
the standard library default is output case:

```javascript
var r = 1;   // 1 = UPPERCASE, 0 = lowercase
```

Python equivalent:
```python
import hashlib
def sha256u(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest().upper()
```

### 1.4 The AD Anti-Tamper Token — Correct Algorithm

Every POST except `LOGIN` and `SET_WEB_LANGUAGE` requires an `AD` field.

The algorithm is split across **three files**:

**`main.js`** — declares globals (misleadingly initialized to empty strings):
```javascript
var rd0 = "";
var rd1 = "";
```

**`login.js`** — overwrites them immediately before login:
```javascript
x.login = function() {
    if (rd0 == "" || rd1 == "") {
        var y = j.getLanguage();   // GET ?cmd=Language,cr_version,wa_inner_version
        rd0 = y.rd_params0;        // = wa_inner_version
        rd1 = y.rd_params1;        // = cr_version
    }
    // ...proceed with login
```

**`service.js`** — `aS()` AJAX wrapper computes AD on every POST:
```javascript
var dy = paswordAlgorithmsCookie(rd0 + rd1);  // SHA256(wa_inner_version + cr_version)
var dx = cA({nv: "RD"}).RD;                   // GET ?cmd=RD  →  fresh session nonce
var dw = paswordAlgorithmsCookie(dy + dx);    // SHA256(prefix + RD)
dt.AD  = dw;
```

**Correct formula:**
```
AD = SHA256_UPPER( SHA256_UPPER(wa_inner_version + cr_version) + RD )
```

**`getLanguage` response** (function `B` in `service.js`):
```
GET /goform/goform_get_cmd_process?isTest=false
    &cmd=Language,cr_version,wa_inner_version&multi_data=1

→ {
    "Language": "en",
    "cr_version":       "7520V3SCSDKV2.01.01.02P42U15",
    "wa_inner_version": "BD_LLCUKRF30PROV1.0.0B01"
  }
```

**RD nonce:**
```
GET /goform/goform_get_cmd_process?isTest=false&cmd=RD
→ {"RD": "DAC5B611D19C01972E4E6CD8..."}
```

`RD` is stable (same value returned on repeated fetches), but is
session-scoped — fetch it immediately before the POST you want to protect.

### 1.5 Wi-Fi Toggle Request

**Turn Wi-Fi OFF:**
```
POST /goform/goform_set_cmd_process
Cookie: stok=<HEX24>
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Origin: http://192.168.0.1
Referer: http://192.168.0.1/index.html

Body: goformId=SET_WIFI_INFO&isTest=false&wifiEnabled=0&AD=<computed>
```

**Turn Wi-Fi ON** (browser also sends `m_ssid_enable`):
```
Body: goformId=SET_WIFI_INFO&isTest=false&wifiEnabled=1&AD=<computed>
```

Source: `service.js` → `function y` (exported as `setWifiBasicMultiSSIDSwitch`):
```javascript
if (dv.wifiEnabled == "0") {
    du = { wifiEnabled: dv.wifiEnabled };   // strip everything else when turning off
}
```

**Success response:** `{"result":"success"}`
**Failure response:** `{"result":"failure"}`

### 1.6 Status Polling Architecture

`service.js` polls the device every ~1 second via `function a9()`:
- Builds a GET request using field list `da` + `aI` (merged when logged in)
- Calls `bF(response)` to update the in-memory status cache `n`
- Key fields polled: `loginfo`, `wifi_cur_state`, `wifi_enable`, `wifi_onoff_func_control`, etc.

`wifi_cur_state` (not `wifi_enable`) is the reliable field for current state:
- `"1"` = Wi-Fi on
- `"0"` = Wi-Fi off

`wifi_enable` and most other settings return `""` (empty string) when
fetched without a valid session or outside of `getWifiBasic()`.

### 1.7 Required Headers

| Header | Value |
|---|---|
| `Content-Type` | `application/x-www-form-urlencoded; charset=UTF-8` |
| `X-Requested-With` | `XMLHttpRequest` |
| `Origin` | `http://192.168.0.1` |
| `Referer` | `http://192.168.0.1/index.html` |
| `Cookie` | `stok=<HEX>` |

The firmware does **not** strictly validate `User-Agent` or `Accept-Language`,
but `X-Requested-With` and `Origin` are necessary.

### 1.8 Full JS File Inventory

| File | Purpose |
|---|---|
| `main.js` | RequireJS bootstrap, declares global `rd0`/`rd1` as `""` |
| `config.js` | Feature flags: `ACCESSIBLE_ID_SUPPORT`, `WEB_ATTR_IF_SUPPORT_SHA256`, etc. |
| `util.js` | SHA-256 implementation (`paswordAlgorithmsCookie`) |
| `service.js` | All API calls, AD computation, status polling (`a9`), response handler (`bF`) |
| `app.js` | Module loader entry point |
| `login.js` | Login UI + **sets `rd0`/`rd1` before login** |
| `statusBar.js` | 500 ms UI status refresh, calls `d.getStatusInfo()` |
| `router.js` | Hash-based SPA routing |

---

## Part 2 — Story of Failure

### Chapter 1 — False assumption from `main.js`

The investigation started correctly: download the JS files, find the AD
computation in `service.js`. The relevant code reads:

```javascript
var dy = paswordAlgorithmsCookie(rd0 + rd1);
```

Checking `main.js`:
```javascript
var rd0 = "";
var rd1 = "";
```

**Fatal assumption:** both variables stay empty for the life of the session.
This made the formula appear to be `AD = SHA256(SHA256("") + RD)`.

This is a natural conclusion — global variable declarations in JavaScript
look authoritative. Nothing in `service.js` or `util.js` reassigns them.

### Chapter 2 — Correct session, wrong hash

After implementing login correctly (result `"0"`, valid `stok`), verified
with `loginfo=ok`, every `SET_WIFI_INFO` POST still returned `{"result":"failure"}`.

Tests ruled out one hypothesis after another:
- Headers (`User-Agent`, `Accept-Encoding`, `Origin`) — no effect
- `m_ssid_enable` extra field — no effect
- Fetching wifi settings before POSTing — no effect
- Curl instead of Python — same failure
- Posting without any AD at all — same `failure` (identical response)

That last point was the confusing part: wrong AD and missing AD produced
**the same response**, making it impossible to tell from the outside
whether the AD was the problem or something else.

The firmware apparently validates `AD` last, after other checks, so an
early-failing check (the stok was valid, but something about the session
state was wrong) masked the AD error entirely.

### Chapter 3 — The one-second polling clue

The user noticed: *"js reads some data each second — maybe this code
modifies the state somehow."*

This triggered a deeper read of `statusBar.js` and `service.js`'s
`function bF` (the poll response handler). `bF` updates the `n` status
cache — network type, wifi state, signal, battery — but does **not**
touch `rd0` or `rd1`.

However, investigating `bF` forced a close read of every function it
called. This led to `function B` (exported as `getLanguage`):

```javascript
function B() {
    // GET ?cmd=Language,cr_version,wa_inner_version
    function ds(du) {
        dt.rd_params0 = du.wa_inner_version;
        dt.rd_params1 = du.cr_version;
        return dt;
    }
}
```

The return value had fields named `rd_params0` and `rd_params1` —
directly matching the globals `rd0` and `rd1`.

### Chapter 4 — The smoking gun in `login.js`

`login.js` had not been downloaded because it was not visible in the
initial network capture (it loads lazily via RequireJS). Once fetched
and read, the assignment was immediately visible:

```javascript
x.login = function() {
    if (rd0 == "" || rd1 == "") {
        var y = j.getLanguage();
        rd0 = y.rd_params0;   // wa_inner_version
        rd1 = y.rd_params1;   // cr_version
    }
```

Every browser login call fetches the firmware version strings and
stores them in the globals before proceeding. The globals are initialized
as `""` in `main.js` purely as a default — they are always overwritten.

With the fix applied the first `SET_WIFI_INFO` POST returned `{"result":"success"}`.

---

## Part 3 — Recommendations for ML Models

### What to do differently

**1. Download ALL JS files before analyzing anything.**

Use the network capture to enumerate every `.js` URL the browser loads,
then fetch them all. RequireJS-based SPAs load modules lazily; the entry
point (`main.js`, `app.js`) won't reveal what gets loaded later.

Minimum set for ZTE firmware:
```
main.js  config.js  util.js  service.js  app.js
login.js  router.js  statusBar.js
config/ufi/<DEVICE>/config.js
```

**2. Never trust initial values of globals — search for ALL assignments.**

When you find `var rd0 = ""`, immediately run:
```
grep -n "rd0\s*=" *.js
```
across every downloaded file. A single `=` anywhere else in the codebase
overrides the declaration. In this case `login.js` was the culprit.

**3. Capture a working browser request with full body before writing code.**

Browser DevTools → Network tab → right-click the POST → "Copy as cURL"
gives the exact body, headers, and cookie. That is the ground truth.
Replicate it first with `curl`, then translate to Python.

For this device, the captured curl would immediately reveal the real AD
value. Working backwards: `AD = SHA256(SHA256(rd0+rd1)+RD)` — since RD
is known (just fetch it), solving for `SHA256(rd0+rd1)` requires only
trying plausible firmware string pairs, which `getLanguage` serves openly.

**4. Test the simplest goformId first.**

`SET_WEB_LANGUAGE` requires no AD and no special state. Use it to
confirm that the session (stok) and headers are accepted before
debugging a more complex command. If `SET_WEB_LANGUAGE` succeeds and
`SET_WIFI_INFO` fails, the problem is specific to that command, not
the session.

**5. When identical responses appear for both valid and invalid inputs,
look upstream.**

`failure` for wrong AD and `failure` for missing AD means the firmware
is rejecting the request before it reaches AD validation. Look for a
state or field the firmware checks first — in this case the AD prefix
was wrong, making the token always invalid regardless of RD.

**6. Follow the call chain for every global variable access.**

When `service.js` reads `rd0`, trace where `rd0` could have been set
by the time that line runs. JavaScript's global scope means any file
in the application can write to it. The declaration file is rarely the
only writer.

### Recommended prompt strategy for a fresh attempt

```
1. "Fetch index.html, then capture all JS file URLs from the network
   requests and download every .js file."

2. "Search every JS file for any assignment to rd0 or rd1 (not just
   declarations)."

3. "In login.js, find the exact sequence of API calls made before
   and during the login() function."

4. "Enable DevTools network capture, log in through the browser,
   navigate to the Wi-Fi settings page, toggle Wi-Fi, click Apply,
   then export the POST request as cURL — including the full request
   body."

5. "Use the captured curl to confirm the request works. Then
   reverse-engineer the AD parameter from the known RD nonce."
```

---

## Part 4 — Could This Be Solved in One Attempt?

**Yes — with the right strategy from the start.**

There are two reliable paths to a one-attempt solution:

### Path A — Browser capture first

1. Open DevTools Network tab before touching the page.
2. Log in, go to Wi-Fi settings, toggle state, click Apply.
3. Copy the POST as cURL. Run it — it works.
4. The stok cookie expires, so automate re-login using the same
   double-SHA256 scheme visible in `service.js`.
5. For the AD: the captured curl shows the AD value. Fetching `RD`
   at the same moment gives the nonce. Solving
   `AD = SHA256(X + RD)` for X gives `SHA256(rd0+rd1)`. Then
   `getLanguage` reveals `rd0` and `rd1` directly.

Total JS analysis needed: **zero** for the initial working curl.
JS analysis for automation: only `service.js` login + AD functions.

### Path B — Full static analysis, correct order

1. Download **all** JS files in the first step.
2. Search for every assignment to `rd0`/`rd1` across all files.
3. Find `login.js` assignment immediately.
4. Read `service.js` AD computation with correct `rd0`/`rd1` values.
5. Implement and run.

This requires knowing to look across all files — not just the ones
that appear most relevant (`service.js`, `util.js`).

### Why the actual session took many iterations

| Mistake | Cost |
|---|---|
| Only downloaded `main.js`, `service.js`, `util.js`, `config.js` | Missed `login.js` entirely |
| Trusted global variable declaration as final value | Wrong AD prefix for every attempt |
| Did not capture browser DevTools POST body | Lost ground truth |
| Identical failure response for multiple distinct problems | Masked which layer was failing |
| Tested `SET_WIFI_INFO` before simpler goformIds | Could not isolate session vs command issues |

### Conclusion

A well-structured one-attempt approach is achievable. The key discipline
is: **get a confirmed working request from the browser before writing
any automation code**, then verify each assumption (session, headers, AD)
in isolation with the simplest possible command before tackling the
target command.

Static JS analysis alone is fragile for this class of problem because:
- RequireJS lazy-loads modules not visible in the initial page source
- Global variables can be written from any loaded module
- Minified single-line files make grepping for all write sites essential

The two-minute browser capture would have bypassed weeks of iteration.
Static analysis remains valuable for understanding *why* things work and
for building a maintainable automation — but it should follow, not
replace, a live capture.
