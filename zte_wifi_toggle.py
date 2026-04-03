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


def set_wifi(host: str, enable: bool) -> None:
    lang = goform_get(host, "Language,cr_version,wa_inner_version&multi_data=1")
    ad_prefix = sha256u(lang["wa_inner_version"] + lang["cr_version"])
    rd = goform_get(host, "RD")["RD"]

    body = urllib.parse.urlencode({
        "goformId": "SET_WIFI_INFO",
        "isTest": "false",
        "wifiEnabled": "1" if enable else "0",
        "AD": sha256u(ad_prefix + rd),
    }).encode()
    req = urllib.request.Request(
        host + "/goform/goform_set_cmd_process", data=body
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())
    if result.get("result") != "success":
        raise RuntimeError(f"Command failed: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Toggle Wi-Fi on ZTE MF935 / F30 Pro")
    parser.add_argument("action", choices=["on", "off"])
    parser.add_argument("--host", default="http://192.168.0.1")
    args = parser.parse_args()

    set_wifi(args.host.rstrip("/"), args.action == "on")
    print(f"Wi-Fi {'enabled' if args.action == 'on' else 'disabled'}.")


if __name__ == "__main__":
    main()
