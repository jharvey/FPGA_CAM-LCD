import uos


def join(*parts):
    out = ""
    for p in parts:
        out = p if p.startswith("/") or not out else out.rstrip("/") + "/" + p
    return out


def dirname(p):
    return p.rsplit("/", 1)[0] if "/" in p else ""


def basename(p):
    return p.rsplit("/", 1)[-1]


def abspath(p):
    return p if p.startswith("/") else uos.getcwd().rstrip("/") + "/" + p


def isfile(p):
    try:
        return uos.stat(p)[0] & 0x8000 != 0
    except OSError:
        return False


exists = isfile
