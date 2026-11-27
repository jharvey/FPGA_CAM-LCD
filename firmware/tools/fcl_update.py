#!/usr/bin/env python3
"""Put new software on the unit over Wi-Fi, without opening it or plugging it in.

    python firmware/tools/fcl_update.py 192.168.1.57 --pin 1234              the Python files of firmware/esp32
    ... --bit fpga/prebuilt/full/fcl_full.bit                                also the FPGA bitstream (until power-off)
    ... --bit fpga/prebuilt/full/fcl_full.bit --flash                        ... and into the FPGA's own memory (stays)
    ... --user my_page.py                                                    your page, stored as fcl_user.py
    ... --dry                                                                only show what would be sent

Before the first use, once, on the USB port: "webpin 1234" (any 4 to 8 digits) and "wifi <name> <password>".  The
address is on the $W line and in the menu's Wi-Fi item.

What it does: asks the unit for its files and their checksums (GET /files), sends only the files that differ
(PUT /f/<name>; the unit keeps the old file unless the new one arrives whole), checks the list again, loads the
bitstream if one was given, and restarts the ESP32.  If a file is refused or differs afterwards, nothing is
restarted and the exit code is 1.  If the unit does not come back, the USB port still works: see doc/TROUBLESHOOTING.md.
"""
import binascii
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ESP = os.path.join(HERE, "..", "esp32")
BIT_NAME = "fcl_full.bit"


def crc_of(data):
    return "%08x" % (binascii.crc32(data) & 0xFFFFFFFF)


class Link:
    def __init__(self, host, pin, timeout=20):
        self.base, self.pin, self.timeout = "http://" + host, pin, timeout

    def _open(self, path, data=None, method=None, headers=None, timeout=None):
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=dict(headers or {}, **{"X-Pin": self.pin}))
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode())
            except ValueError:
                return {"ok": False, "error": "HTTP %d" % e.code}

    def files(self):
        return dict((f["name"], f) for f in self._open("/files"))

    def put(self, name, data):
        return self._open("/f/" + name, data, "PUT", {"X-Crc": crc_of(data)}, timeout=120)

    def command(self, line, timeout=None):
        r = self._open("/c", line.encode(), "POST", timeout=timeout)
        return r.get("ok", False), (r.get("lines") or [r.get("error", "")])[-1]


def local_files(user=None):
    """{name on the unit: bytes}: every .py of firmware/esp32, and the user's page as fcl_user.py"""
    out = {}
    for n in sorted(os.listdir(ESP)):
        if n.endswith(".py"):
            out[n] = open(os.path.join(ESP, n), "rb").read()
    if user:
        out["fcl_user.py"] = open(user, "rb").read()
    return out


def update(link, files, bit=None, flash=False, dry=False, reboot=True, say=print):
    """-> True when the unit has every file.  files: {name: bytes}"""
    have = link.files()
    todo = [n for n in sorted(files) if n not in have or have[n]["crc"] != crc_of(files[n])]
    say("%d files here, %d on the unit, %d to send%s" % (len(files), len(have), len(todo), ": " + " ".join(todo) if todo else ""))
    if bit is not None:
        same = BIT_NAME in have and have[BIT_NAME]["size"] == len(bit)
        say("bitstream %d bytes%s" % (len(bit), " (a file of this size is on the unit; sent again to be sure)" if same else ""))
    if dry:
        return True
    for n in todo:
        r = link.put(n, files[n])
        if not r.get("ok"):
            say("  %-22s REFUSED: %s" % (n, r.get("error", r)))
            return False
        say("  %-22s %6d bytes  sent" % (n, len(files[n])))
    if bit is not None:
        r = link.put(BIT_NAME, bit)
        if not r.get("ok") or r.get("crc") != crc_of(bit):
            say("  %-22s REFUSED: %s" % (BIT_NAME, r.get("error", r)))
            return False
        say("  %-22s %6d bytes  sent, checksum %s" % (BIT_NAME, len(bit), r["crc"]))
    have = link.files()
    wrong = [n for n in files if n not in have or have[n]["crc"] != crc_of(files[n])]
    if wrong:
        say("the unit's files differ after sending: " + " ".join(wrong))
        return False
    if bit is not None:
        ok, text = link.command("fpga %s%s" % (BIT_NAME, " flash" if flash else ""), timeout=240)
        say("  " + text)
        if not ok or "failed" in text:
            return False
    if reboot and (todo or bit is not None):
        ok, text = link.command("reboot")
        say("  restart: " + text)
    elif not todo:
        say("nothing to do: the unit is up to date")
    return True


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("host", help="the unit's address, as on its $W line (add :port for the simulator)")
    ap.add_argument("--pin", required=True, help="the PIN set on the USB port with webpin")
    ap.add_argument("--bit", help="FPGA bitstream file to send and load")
    ap.add_argument("--flash", action="store_true", help="write the bitstream into the FPGA's configuration memory")
    ap.add_argument("--user", help="a page of your own, stored as fcl_user.py")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-reboot", action="store_true")
    a = ap.parse_args()
    link = Link(a.host, a.pin)
    try:
        ok = update(link, local_files(a.user), open(a.bit, "rb").read() if a.bit else None, a.flash, a.dry, not a.no_reboot)
    except (OSError, ValueError) as e:
        print("no answer from %s: %s" % (a.host, e))
        return 1
    if ok and not a.dry and not a.no_reboot:
        time.sleep(1)
        print("done; the unit takes about 10 s to start again")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
