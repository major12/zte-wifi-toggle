# Code Optimization: Questioning Every Assumption

## The Story

The first working version of `zte_wifi_toggle.py` was 131 lines. It had been built
incrementally during reverse engineering — each piece added when something broke.
By the time it worked, it carried every safeguard that had ever been tried:

- A `CookieJar` to manage session cookies automatically
- A full browser-like header block (User-Agent, Accept, Accept-Language,
  X-Requested-With, Origin, Referer, Content-Type)
- A `login()` function that fetched `LD`, hashed the password twice, and extracted
  the `stok` cookie from `Set-Cookie`
- The `stok` cookie forwarded on every subsequent request
- `sys.argv` parsed manually

None of this was wrong — it had all been observed in the browser's network traffic.
But "observed in the browser" is not the same as "required by the server."

The simplification happened in rounds:

**Round 1 — cosmetic cleanup**: `sys.argv` → `argparse`, long docstring → one line,
`http.cookiejar` replaced by a regex on `Set-Cookie`. Still 131 lines, just tidier.

**Round 2 — the real question**: *Is `stok` actually checked?*
One test: send `SET_WIFI_INFO` without the cookie. Result: `{"result":"success"}`.
The cookie was never necessary.

**Round 3 — follow the thread**: *If the cookie isn't checked, is login checked?*
Send the command with no login at all — just `AD`. Result: `{"result":"success"}`.
Login, `stok`, and `LD` were all dead weight. Removed entirely.

**Round 4 — naming**: `get` → `query` → `goform_get`. Each name more precise than
the last, matching the actual endpoint name `goform_get_cmd_process`.

Final result: 47 lines. No session management, no headers, no login, no cookies.
Three HTTP calls: fetch versions, fetch nonce, post command.

---

## Recommendations for This Class of Optimization

When a working script has been built by tracing browser traffic, always run a
second pass with this checklist. The browser is maximally defensive; scripts
should be minimally so.

### 1. Test every parameter for necessity

For each piece of data sent (headers, cookies, body fields, query params), ask:
*what happens if I omit this?* Then actually omit it and run the request.

```
Prompt: "For each header / cookie / field in this request, test whether
omitting it changes the server response. Remove anything that doesn't."
```

Do not assume a parameter is required because the browser sends it. Browsers
send many things for compatibility, caching, and security that embedded firmware
simply ignores.

### 2. Question authentication layers separately

Authentication often has multiple layers (session cookie, login token, signed
parameter). Test each layer independently:

- Does the signed parameter (`AD`) work without the session cookie (`stok`)?
- Does the signed parameter work without prior login?
- Can the nonce (`RD`) be fetched without authentication?

```
Prompt: "This API has N authentication mechanisms. Test each one in isolation
by omitting the others. Identify the minimal set the server actually enforces."
```

### 3. Start from the server's perspective, not the browser's

The browser's job is to work on every server. The script's job is to work on
*this* server. Treat browser traffic as a starting hypothesis, not a specification.

```
Prompt: "The browser sends X. Assume X is not required until proven otherwise.
Prove it by testing without X."
```

### 4. Apply KISS as a forcing function

After each simplification, ask: *what is the simplest code that passes the same
tests?* If the answer differs from the current code, simplify.

Common sources of unnecessary complexity in HTTP scripts built from browser traces:

| Browser artifact | Usually necessary? |
|---|---|
| User-Agent header | Rarely |
| Accept / Accept-Language headers | Rarely |
| X-Requested-With: XMLHttpRequest | Sometimes (CSRF guard) — test it |
| Origin / Referer headers | Sometimes — test it |
| Session cookies | Sometimes — test it |
| Login step | Sometimes — test it |
| Content-Type on POST | Yes — urllib sets it automatically |

### 5. Test incrementally, not all at once

Remove one thing at a time and verify the result still works before removing the
next. If you remove everything at once and it breaks, you learn nothing useful.

```
Prompt: "Remove parameters one at a time, testing after each removal.
Stop only when removing the next parameter causes failure."
```

### 6. Let naming follow simplification

Names chosen early often reflect implementation details that later disappear.
After simplifying, revisit every name:

- Does the function name describe what it *does*, not how it was *implemented*?
- Does the name match the protocol concept (e.g. `goform_get` for
  `goform_get_cmd_process`)?
- Are constants that get mutated actually constants? If not, make them parameters.

```
Prompt: "After simplification, review all names. Rename anything that reflects
a removed concept or a misleading level of generality."
```
