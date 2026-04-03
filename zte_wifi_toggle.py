#!/usr/bin/env python3
"""
ZTE MF935 / F30 Pro  -  Wi-Fi on/off automation
================================================
AD parameter algorithm (traced through login.js + service.js):

  login.js  - BEFORE calling login(), the browser does:
      if(rd0 == "" || rd1 == "") {
          var y = j.getLanguage();     // GET ?cmd=Language,cr_version,wa_inner_version
          rd0 = y.rd_params0;          // = wa_inner_version  (firmware build string)
          rd1 = y.rd_params1;          // = cr_version        (SDK version string)
      }

  service.js - aS() AJAX wrapper computes AD for every POST except LOGIN/SET_WEB_LANGUAGE:
      var dy = paswordAlgorithmsCookie(rd0 + rd1);   // SHA256(wa_inner_version + cr_version)
      var dx = cA({nv:"RD"}).RD;                     // GET ?cmd=RD  (fresh session nonce)
      var dw = paswordAlgorithmsCookie(dy + dx);      // SHA256(prefix + RD)
      dt.AD  = dw;

  util.js - SHA256() outputs UPPERCASE hex (r=1 flag in the implementation).

  Correct formula:
      AD = SHA256_UPPER( SHA256_UPPER(wa_inner_version + cr_version) + RD )

Login password hash (WEB_ATTR_IF_SUPPORT_SHA256 == 2, from config.js):
    login_pw = SHA256_UPPER( SHA256_UPPER(plaintext_password) + LD )
"""

import hashlib
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://192.168.0.1"
PASSWORD = "admin"

HEADERS = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "uk,en-US;q=0.9,en;q=0.8",
    "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin":           BASE,
    "Referer":          BASE + "/index.html",
}


def sha256u(s: str) -> str:
    """SHA-256 of UTF-8 string, UPPERCASE hex - mirrors ZTE's paswordAlgorithmsCookie."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest().upper()


def build_opener() -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get_json(opener, path: str) -> dict:
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    with opener.open(req, timeout=20) as r:
        return json.loads(r.read().decode())


def post(opener, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        BASE + "/goform/goform_set_cmd_process",
        data=body,
        headers=HEADERS,
        method="POST",
    )
    with opener.open(req, timeout=20) as r:
        return json.loads(r.read().decode())


def get_ad_prefix(opener) -> str:
    """Mirrors login.js: fetch wa_inner_version+cr_version and hash them (the rd0/rd1 values)."""
    lang = get_json(
        opener,
        "/goform/goform_get_cmd_process?isTest=false&cmd=Language%2Ccr_version%2Cwa_inner_version&multi_data=1",
    )
    rd0 = lang.get("wa_inner_version", "")
    rd1 = lang.get("cr_version", "")
    return sha256u(rd0 + rd1)


def login(opener) -> None:
    ld = get_json(opener, "/goform/goform_get_cmd_process?isTest=false&cmd=LD")["LD"]
    login_pw = sha256u(sha256u(PASSWORD) + ld)
    result = post(opener, {"goformId": "LOGIN", "isTest": "false", "password": login_pw})
    if str(result.get("result")) not in ("0", "4"):
        raise RuntimeError(f"Login failed: {result}")


def set_wifi(opener, enabled: bool, ad_prefix: str) -> dict:
    rd = get_json(opener, "/goform/goform_get_cmd_process?isTest=false&cmd=RD")["RD"]
    ad = sha256u(ad_prefix + rd)
    return post(opener, {
        "goformId":    "SET_WIFI_INFO",
        "isTest":      "false",
        "wifiEnabled": "1" if enabled else "0",
        "AD":           ad,
    })


def main() -> int:
    action = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if action not in ("on", "off"):
        print("Usage: python zte_wifi_toggle.py [on|off]")
        return 1

    opener = build_opener()
    ad_prefix = get_ad_prefix(opener)
    login(opener)

    enabled = action == "on"
    result = set_wifi(opener, enabled, ad_prefix)

    if result.get("result") == "success":
        print(f"Wi-Fi {'enabled' if enabled else 'disabled'} successfully.")
        return 0
    else:
        print(f"Failed: {result}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
