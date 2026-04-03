# zte-wifi-toggle

CLI script to turn Wi-Fi on or off on a ZTE MF935 / F30 Pro mobile hotspot without touching the browser.

## Usage

```bash
python zte_wifi_toggle.py on
python zte_wifi_toggle.py off
```

## Configuration

Edit the top of `zte_wifi_toggle.py` to change defaults:

| Variable   | Default           | Description              |
|------------|-------------------|--------------------------|
| `BASE`     | `http://192.168.0.1` | Router address        |
| `PASSWORD` | `admin`           | Admin password           |

## How it works

The router's web UI uses a custom anti-tamper token (`AD`) on every POST request. It is computed from firmware version strings that are fetched before login:

```
rd0 = wa_inner_version   (e.g. "BD_LLCUKRF30PROV1.0.0B01")
rd1 = cr_version         (e.g. "7520V3SCSDKV2.01.01.02P42U15")

AD = SHA256( SHA256(rd0 + rd1) + RD )
```

Where `RD` is a fresh per-session nonce from the device, and `SHA256` outputs uppercase hex — matching the device's own `paswordAlgorithmsCookie()` implementation in `util.js`.

The login password is double-hashed with a separate nonce:

```
login_pw = SHA256( SHA256(password) + LD )
```

## Requirements

Python 3.9+ — no third-party dependencies.
