#!/usr/bin/env python3
"""Toggle Wi-Fi on a ZTE MF935 / F30 Pro hotspot. See ANALYSIS.md for protocol details."""

import argparse
import hashlib
import json
import urllib.parse
import urllib.request


def sha256u(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest().upper()


def goform_get(host: str, cmd: str) -> dict:
    url = host + "/goform/goform_get_cmd_process?isTest=false&cmd=" + cmd
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def goform_post(host: str, fields: dict) -> dict:
    body = urllib.parse.urlencode({"isTest": "false", **fields}).encode()
    with urllib.request.urlopen(
        urllib.request.Request(host + "/goform/goform_set_cmd_process", data=body),
        timeout=15,
    ) as r:
        return json.loads(r.read())


def login(host: str, password: str) -> None:
    # Login initializes server-side RD state; the returned stok cookie is not needed.
    ld = goform_get(host, "LD")["LD"]
    goform_post(host, {"goformId": "LOGIN", "password": sha256u(sha256u(password) + ld)})


def set_wifi(host: str, enable: bool) -> None:
    info = goform_get(host, "RD,cr_version,wa_inner_version&multi_data=1")
    ad = sha256u(sha256u(info["wa_inner_version"] + info["cr_version"]) + info["RD"])
    result = goform_post(host, {
        "goformId": "SET_WIFI_INFO",
        "wifiEnabled": "1" if enable else "0",
        "AD": ad,
    })
    if result.get("result") != "success":
        raise RuntimeError(f"Command failed: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Toggle Wi-Fi on ZTE MF935 / F30 Pro")
    parser.add_argument("action", choices=["on", "off"])
    parser.add_argument("--host", default="http://192.168.0.1")
    parser.add_argument("--password", default="admin")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    login(host, args.password)
    set_wifi(host, args.action == "on")
    print(f"Wi-Fi {'enabled' if args.action == 'on' else 'disabled'}.")


if __name__ == "__main__":
    main()
