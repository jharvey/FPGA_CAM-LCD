#!/usr/bin/env python3
"""Printable copies of two documents: doc/QUICK_START.pdf (one page) and doc/BRINGUP.pdf (the checklist, with room
to write in the Result columns).

    python firmware/tools/make_pdf.py          needs the Python package "markdown" and Edge or Chrome
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.abspath(os.path.join(HERE, "..", "..", "doc"))

CSS = """
@page { size: A4 %(orient)s; margin: %(margin)s; }
body { font: %(size)s/1.35 "Segoe UI", Helvetica, Arial, sans-serif; color: #000; }
h1 { font-size: 1.6em; margin: 0 0 .3em; } h2 { font-size: 1.2em; margin: .9em 0 .3em; border-bottom: 1px solid #999; }
h3 { font-size: 1.05em; margin: .8em 0 .2em; } p, ul, ol { margin: .35em 0; } li { margin: .1em 0; }
table { border-collapse: collapse; width: 100%%; margin: .4em 0; page-break-inside: auto; }
tr { page-break-inside: avoid; } th, td { border: 1px solid #777; padding: 2px 5px; vertical-align: top; text-align: left; }
th { background: #e8e8e8; } code { font: .92em Consolas, monospace; } pre { background: #f2f2f2; padding: 4px 6px; white-space: pre-wrap; }
a { color: #000; text-decoration: none; } img { max-width: 100%%; }
%(extra)s
"""


def browser():
    for p in (os.environ.get("BROWSER"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if p and os.path.exists(p):
            return p
    raise SystemExit("no Edge / Chrome found (set BROWSER=/path/to/it)")


def make(name, orient="portrait", size="9.5pt", margin="12mm", extra="", drop=()):
    import markdown
    text = open(os.path.join(DOC, name + ".md"), encoding="utf-8").read()
    for line in drop:                                    # lines that only make sense on a screen
        text = "\n".join(x for x in text.split("\n") if line not in x)
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    html = "<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>%s</body></html>" % (
        name, CSS % {"orient": orient, "size": size, "margin": margin, "extra": extra}, body)
    tmp = os.path.join(DOC, "_" + name + ".html")        # beside the document, so that its pictures are found
    open(tmp, "w", encoding="utf-8").write(html)
    pdf = os.path.join(DOC, name + ".pdf")
    prof = os.path.join(DOC, "_pdf_profile")
    try:
        subprocess.run([browser(), "--headless", "--disable-gpu", "--no-sandbox", "--user-data-dir=" + prof, "--no-pdf-header-footer",
                        "--print-to-pdf=" + pdf, "file:///" + tmp.replace("\\", "/")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=120)
    finally:
        os.remove(tmp)
        shutil.rmtree(prof, ignore_errors=True)
    print("wrote" if os.path.exists(pdf) else "NOT written:", pdf, os.path.getsize(pdf) if os.path.exists(pdf) else "")


if __name__ == "__main__":
    make("QUICK_START", size="8.6pt", margin="10mm", drop=("A printable copy of this page",))
    # the checklist: landscape, and wide last columns to write the measured values in
    make("BRINGUP", orient="landscape", size="8.5pt", extra="td:last-child, th:last-child { min-width: 34mm; }")
    sys.exit(0)
