# The unit as a web page over Wi-Fi: the LCD text and graphics, the readings, buttons for the everyday commands,
# the log files, and a way to put new files on the unit.
# Runs on the ESP32 (MicroPython, started by fcl_usbdev.py on port 80) and on a PC (python fcl_sim.py --web 8080).
#
#   web = Web(usb, hub, plat, port=80, root="")      usb: fcl_usb.Bridge; root: folder of the unit's files
#   web.poll()                              call from the main loop; never waits for a slow client
#
#   GET /            the page (one file, no outside scripts, works without internet)
#   GET /s           state as JSON: telemetry, LCD rows, graphics, Wi-Fi, compass calibration, servos
#   POST /c          one command line of fcl_usb.py in the body -> {"ok": true, "lines": [...]}
#   GET /files       [{"name", "size", "crc"}] of the .py, .bit and .log files (crc: CRC-32 as 8 hex digits,
#                    null for files over 64 kB)
#   GET /f/<name>    one of those files (a log, for instance), sent in pieces between sensor frames
#   PUT /f/<name>    store a .py or .bit file (header X-Crc: its CRC-32).  Written beside the old file and put
#                    in its place only when the length and the CRC are right.  Used by firmware/tools/fcl_update.py
#
# Who may do what.  Anyone on the same network can open the page and press its buttons: the commands in ALLOWED.
# The commands in PIN_ALLOWED (calibration values, restart, load the FPGA) and every PUT need the PIN in the header
# X-Pin.  The PIN is set on the USB port only ("webpin 1234"); with no PIN set these are refused.  Five wrong PINs
# lock them for a minute.  The PIN travels unencrypted: it keeps a stranger on the same Wi-Fi from changing the
# unit; it is not protection against someone who can listen to the network.  Wi-Fi settings, audio and the
# Python prompt stay on the USB port.
import json
import os
import socket
import time
try:
    from binascii import crc32
except ImportError:
    from ubinascii import crc32

ALLOWED = ("key", "mode", "view", "threshold", "overlay", "hud", "zero", "follow", "servo", "pan", "magcal", "log", "tone",
           "status", "points")
PIN_ALLOWED = ("cal", "reboot", "fpga")
SERVED = ("py", "bit", "log")           # file types GET /f gives out
STORED = ("py", "bit")                  # file types PUT /f takes
MAX_UPLOAD = 2000000
PIN_FILE = "webpin.txt"

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FCL monocular</title><style>
:root{--bg:#f4f5f2;--card:#fff;--ink:#1c2321;--dim:#66706c;--line:#d9ddd7;--acc:#0a7d5a;--warn:#b25c00;--bad:#b3261e}
@media(prefers-color-scheme:dark){:root{--bg:#121514;--card:#1c2120;--ink:#e8ece9;--dim:#98a39e;--line:#2c3331;--acc:#4fd1a1;--warn:#f0a94a;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 system-ui,sans-serif}
main{max-width:460px;margin:0 auto;padding:12px 16px 32px}h1{font-size:17px;margin:4px 0 10px;display:flex;justify-content:space-between}
#link{font-weight:400;color:var(--dim);font-size:14px}#link.bad{color:var(--bad)}
svg{display:block;width:100%;max-width:340px;margin:0 auto 12px}#ch{max-width:none;height:56px;margin:4px 0 0}
#pin{font:inherit;width:100%;padding:9px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
a{color:var(--acc)}#files a{display:inline-block;margin:2px 10px 2px 0}
.g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px}.c{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.c small{display:block;color:var(--dim);font-size:12px}.c b{font-size:22px;font-variant-numeric:tabular-nums}.c span{color:var(--dim);font-size:13px}
.w{grid-column:1/3}.bar{height:8px;border-radius:4px;background:var(--line);margin:4px 0 6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
.bar i.low{background:var(--warn)}.cell{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.k{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
button{font:inherit;padding:11px 4px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
button:active{background:var(--acc);color:var(--bg)}button.on{border-color:var(--acc);color:var(--acc)}
#msg{color:var(--dim);font-size:13px;min-height:20px;margin-top:8px}
</style></head><body><main>
<h1>FCL monocular <span id="link">connecting</span></h1>
<svg viewBox="0 0 480 480" role="img" aria-label="LCD text"><defs><clipPath id="r"><circle cx="240" cy="240" r="240"/></clipPath></defs>
<circle cx="240" cy="240" r="240" fill="#26302d"/><g id="lcd" clip-path="url(#r)" fill="#fff" font-family="monospace" font-weight="700" font-size="27"></g>
<g id="hud" clip-path="url(#r)" fill="none" stroke-linecap="butt"></g>
<g id="dot"><circle r="13" fill="#000"/><circle r="9.5" fill="none" stroke-width="3"/><circle r="3"/></g></svg>
<div class="g">
<div class="c"><small>Heading</small><b id="hd">-</b> <span id="card"></span></div>
<div class="c"><small>Pitch / roll</small><b id="pr">-</b></div>
<div class="c"><small>Height</small><b id="alt">-</b> <span id="hpa"></span></div>
<div class="c"><small>Distance</small><b id="dist">-</b></div>
<div class="c w"><small>Cells</small><div class="cell" id="cells"></div></div>
<div class="c w"><small>Height, last minute <span id="chr"></span></small><svg id="ch" viewBox="0 0 300 56" preserveAspectRatio="none">
<polyline id="chl" fill="none" stroke="var(--acc)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg></div>
<div class="c w"><small>Status</small><span id="st">-</span></div>
</div>
<div class="k">
<button data-c="key B1">B1 page</button><button data-c="key B2">B2 action</button><button data-c="key B1L">Menu</button>
<button id="view">View</button><button data-c="zero">Zero height</button><button id="foll">Level servo</button>
<button id="ovl">Overlay</button><button id="log">Log</button><button id="pan">Pan hold</button>
<button id="gfx">Graphics</button><button id="trim">Level trim</button><button data-c="magcal start">Compass cal</button>
</div><div id="msg"></div>
<div class="g" style="margin-top:10px"><div class="c w"><small>Log files on the unit</small><span id="files">-</span></div>
<div class="c w"><small>PIN, for Level trim and updates (set on the USB port: webpin 1234)</small>
<input id="pin" type="password" inputmode="numeric" autocomplete="off" aria-label="PIN"></div></div></main><script>
var S=null,A=[],C=["N","NE","E","SE","S","SW","W","NW"],$=function(i){return document.getElementById(i)};
try{$("pin").value=localStorage.getItem("fclpin")||""}catch(e){}
$("pin").onchange=function(){try{localStorage.setItem("fclpin",$("pin").value)}catch(e){}};
function send(c){fetch("/c",{method:"POST",body:c,headers:{"X-Pin":$("pin").value}}).then(function(r){return r.json()}).then(function(j){
$("msg").textContent=c+": "+(j.lines.length?j.lines[j.lines.length-1].replace(/^\\$R,/,""):"")}).catch(function(){$("msg").textContent=c+": no answer"})}
document.querySelectorAll("button[data-c]").forEach(function(b){b.onclick=function(){send(b.dataset.c)}});
$("view").onclick=function(){send("view "+(S&&S.edges?"camera":"edges"))};
$("foll").onclick=function(){send("follow "+(S&&S.follow?"off":"on"))};
$("ovl").onclick=function(){var m=S?S.t.overlay:63;send("overlay "+(m==63?1:m==1?0:63))};
$("log").onclick=function(){send("log "+(S&&S.log?"off":"on"))};
$("pan").onclick=function(){send("pan "+(S&&S.pan!=null?"off":"here"))};
$("gfx").onclick=function(){var m=S?S.gfx:0;send("hud "+(m==0?1:m==1?7:0))};
$("trim").onclick=function(){if(!S)return;send("cal set pitch0 "+(S.cal.pitch0+S.t.pitch).toFixed(1));
setTimeout(function(){send("cal set roll0 "+(S.cal.roll0+S.t.roll).toFixed(1))},400)};
function L(x1,y1,x2,y2,w,c){return'<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="'+c+'" stroke-width="'+w+'"/>'}
function hud(u){var f=u[0],a=u[1],b=u[2],c=u[3],h="",i,k,x;
if(f&4){h+='<rect x="152" y="18" width="176" height="12" fill="#000" fill-opacity=".5" stroke="none"/>';
for(x=152;x<328;x++){k=(x+16+u[4])&31;if(k==0)h+=L(x+1,18,x+1,30,2,"#fff");if(k==16)h+=L(x+1,24,x+1,30,2,"#fff")}h+=L(240,10,240,16,3,"#fff")}
if(f&2){var n=a*a+b*b,px=240-128*c*a/n,py=240-128*c*b/n,q=Math.sqrt(n),ux=b/q,uy=-a/q;
for(i=-1;i<2;i+=2)for(k=0;k<2;k++)h+=L(px+i*48*ux,py+i*48*uy,px+i*176*ux,py+i*176*uy,k?2:5,k?"#fff":"#000")}
if(f&1)for(k=0;k<2;k++){var w=k?1.5:4,o=k?"#fff":"#000";h+=L(211,240,234,240,w,o)+L(246,240,269,240,w,o)+L(240,211,240,234,w,o)+L(240,246,240,269,w,o)+L(239,240,241,240,w,o)}
$("hud").innerHTML=h}
function chart(v){A.push(v);if(A.length>200)A.shift();var lo=Math.min.apply(null,A),hi=Math.max.apply(null,A),r=Math.max(hi-lo,.2),p="",i;
for(i=0;i<A.length;i++)p+=(300*i/199).toFixed(1)+","+(52-48*(A[i]-lo)/r).toFixed(1)+" ";
$("chl").setAttribute("points",p);$("chr").textContent=lo.toFixed(2)+" to "+hi.toFixed(2)+" m"}
function files(){fetch("/files").then(function(r){return r.json()}).then(function(l){var h="";l.forEach(function(f){
if(/\\.log$/.test(f.name))h+='<a href="/f/'+f.name+'" download>'+f.name+"</a> "+Math.round(f.size/1024)+" kB "});
$("files").innerHTML=h||"none"}).catch(function(){}).then(function(){setTimeout(files,10000)})}
function show(s){S=s;var t=s.t,g=$("lcd"),h="",i;
for(i=0;i<15;i++){var row=(s.lcd[i]||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");
if(row.trim())h+='<text x="0" y="'+(i*32+25)+'" textLength="480" lengthAdjust="spacingAndGlyphs" xml:space="preserve">'+row+"</text>"}
g.innerHTML=h;var d=$("dot"),on=(t.overlay&1)&&!s.menu,col=(t.flags&32)?"#28ff50":"#ffb000";
d.style.display=on?"":"none";d.setAttribute("transform","translate("+(240+t.dot_x)+","+(240+t.dot_y)+")");
d.children[1].setAttribute("stroke",col);d.children[2].setAttribute("fill",col);
$("hd").textContent=Math.round(t.heading)%360+"\\u00b0";$("card").textContent=C[Math.round(t.heading/45)%8];
$("pr").textContent=t.pitch.toFixed(1)+"\\u00b0 / "+t.roll.toFixed(1)+"\\u00b0";
$("alt").textContent=(t.alt_m>=0?"+":"")+t.alt_m.toFixed(2)+" m";$("hpa").textContent=(t.press_pa/100).toFixed(1)+" hPa";
$("dist").textContent=(t.flags&8)?(t.tof_mm/1000).toFixed(2)+" m":"out of range";
h="";for(i=1;i<=3;i++){var p=t["soc"+i],no=p==255;h+="<div><b>"+(no?"--":p+"%")+'</b><div class="bar"><i class="'+(p<15?"low":"")+'" style="width:'+(no?0:p)+
'%"></i></div><span>'+(no?"no cell":(t["cell"+i+"_mv"]/1000).toFixed(2)+" V, "+t["temp"+i+"_c"].toFixed(0)+" \\u00b0C")+"</span></div>"}
$("cells").innerHTML=h;
$("st").textContent="page "+s.page+(s.menu?", menu open":"")+(t.flags&1?", REC":"")+(t.flags&2?", cell low":"")+(t.flags&16?", hot":"")+
", Wi-Fi "+s.wifi[0]+(s.wifi[2]?" "+s.wifi[2]:"")+", compass "+s.mag.split(",")[0];
$("view").textContent="View: "+(s.edges?"edges":"camera");$("foll").className=s.follow?"on":"";$("log").className=s.log?"on":"";
$("log").textContent=s.log?"Log on":"Log";$("pan").className=s.pan!=null?"on":"";$("pan").textContent=s.pan!=null?"Pan "+Math.round(s.pan)+"\\u00b0":"Pan hold";
$("ovl").textContent="Overlay: "+(t.overlay==63?"all":t.overlay==1?"dot":t.overlay==0?"off":"custom");
$("gfx").textContent="Graphics: "+(s.gfx==0?"page":s.gfx==1?"reticle":s.gfx==7?"all":"custom");hud(s.hud);chart(t.alt_m)}
function tick(){fetch("/s").then(function(r){return r.json()}).then(function(s){$("link").textContent="live";$("link").className="";if(s.t&&s.t.heading!=null)show(s)})
.catch(function(){$("link").textContent="no connection";$("link").className="bad"}).then(function(){setTimeout(tick,300)})}
tick();files();</script></body></html>
"""


def _ext(name):
    return name.rsplit(".", 1)[-1] if "." in name else ""


def _name_ok(name):
    """a plain file name: letters, digits, _ - . only, no folders"""
    if not name or len(name) > 40 or name[0] == ".":
        return False
    for ch in name:
        if not (ch.isalpha() or ch.isdigit() or ch in "_-."):
            return False
    return True


class Web:
    def __init__(self, usb, hub, plat=None, port=80, root=""):
        self.usb, self.hub, self.plat = usb, hub, plat
        self.root = root                 # "" on the ESP32 (its flash); a folder with a trailing / on a PC
        usb.web = self                   # for the USB command "webpin"
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(socket.getaddrinfo("0.0.0.0", port)[0][-1])
        s.listen(2)
        s.setblocking(False)
        self.s = s
        self.port = port
        self.conns = []                  # [socket, bytearray received, polls waited, mode, context]
        self.requests = 0                #   mode 0 reading a request, 1 receiving a file, 2 sending a file
        self.pin = ""
        self.bad, self.lock_t = 0, 0
        try:
            with open(root + PIN_FILE) as f:
                self.pin = f.read().strip()
        except OSError:
            pass

    def close(self):
        for conn in self.conns[:]:
            self._drop(conn)
        self.s.close()

    # ---- the PIN
    def set_pin(self, pin):
        """4 to 8 digits, or "" for none.  Called from the USB port only."""
        if pin and not (4 <= len(pin) <= 8 and pin.isdigit()):
            raise ValueError("the PIN is 4 to 8 digits")
        self.pin = pin
        if pin:
            with open(self.root + PIN_FILE, "w") as f:
                f.write(pin)
        else:
            try:
                os.remove(self.root + PIN_FILE)
            except OSError:
                pass

    def _pin_ok(self, hdr):
        """-> "" when the request carries the right PIN, else the reason it is refused"""
        if not self.pin:
            return "no PIN is set: set one on the USB port (webpin 1234)"
        if time.time() < self.lock_t:
            return "too many wrong PINs: wait a minute"
        if hdr.get("x-pin", "") == self.pin:
            self.bad = 0
            return ""
        self.bad += 1
        if self.bad >= 5:
            self.bad, self.lock_t = 0, time.time() + 60
        return "this needs the PIN"

    # ---- what the page shows
    def state(self):
        hub = self.hub
        f = getattr(self.plat, "wifi_status", None)
        apps = hub.apps
        app = apps.pages[hub.mode_n] if hub.mode_n < len(apps.pages) else None
        cfg = hub.cfg.v
        return {"t": hub.last, "lcd": hub.osd, "page": "OVERVIEW" if app is None else app.name, "menu": apps.menu_open,
                "wifi": list(f()) if f else ["off", "", "", 0], "mag": hub.cal.status(), "servos": self.usb.servos,
                "log": apps.log_on, "edges": hub.edges, "follow": hub.follow_on, "pan": hub.pan_target,
                "hud": list(hub.hud), "gfx": hub.hud_mask, "cal": {"pitch0": cfg["pitch0"], "roll0": cfg["roll0"]},
                "pin": bool(self.pin)}

    def command(self, line, hdr=None):
        a = line.strip().split()
        name = a[0].lower() if a else ""
        if name in PIN_ALLOWED:
            why = self._pin_ok(hdr or {})
            if why:
                return {"ok": False, "lines": ["$R,err," + why]}
        elif name not in ALLOWED:
            return {"ok": False, "lines": ["$R,err,not available on the web page: " + name]}
        usb = self.usb
        usb.capture = []
        try:
            usb.command(line)
            lines = usb.capture
        finally:
            usb.capture = None
        return {"ok": bool(lines) and lines[-1].startswith("$R,ok"), "lines": lines}

    def files(self):
        out = []
        for name in sorted(os.listdir(self.root or ".")):
            if _ext(name) not in SERVED or not _name_ok(name):
                continue
            size = os.stat(self.root + name)[6]
            crc = None
            if size <= 65536:
                c = 0
                with open(self.root + name, "rb") as f:
                    while True:
                        d = f.read(1024)
                        if not d:
                            break
                        c = crc32(d, c)
                crc = "%08x" % (c & 0xFFFFFFFF)
            out.append({"name": name, "size": size, "crc": crc})
        return out

    # ---- sockets
    def poll(self):
        try:
            c, _ = self.s.accept()
            c.setblocking(False)
            if len(self.conns) >= 4:
                self._drop(self.conns[0])
            self.conns.append([c, bytearray(), 0, 0, None])
        except OSError:
            pass
        for conn in self.conns[:]:
            c, buf = conn[0], conn[1]
            if conn[3] == 2:
                self._pump(conn)
                continue
            try:
                d = c.recv(1460)
            except OSError:
                conn[2] += 1
                if conn[2] > 2000:                       # a client that never finishes its request
                    self._drop(conn)
                continue
            if not d:
                self._drop(conn)
                continue
            conn[2] = 0
            if conn[3] == 1:
                self._body(conn, d)
                continue
            buf.extend(d)
            i = bytes(buf).find(b"\r\n\r\n")
            if i < 0:
                if len(buf) > 2048:
                    self._drop(conn)
                continue
            lines = bytes(buf[:i]).decode("utf-8", "replace").split("\r\n")
            req = lines[0].split(" ")
            hdr = {}
            for h in lines[1:]:
                if ":" in h:
                    k, v = h.split(":", 1)
                    hdr[k.strip().lower()] = v.strip()
            try:
                n = int(hdr.get("content-length", "0"))
            except ValueError:
                n = 0
            method, path = req[0], req[1] if len(req) > 1 else "/"
            if method == "PUT" and path.startswith("/f/"):
                self.requests += 1
                self._put(conn, path[3:], hdr, n, bytes(buf[i + 4:]))
                continue
            if len(buf) < i + 4 + n:
                continue
            self.requests += 1
            if not self._answer(conn, method, path, hdr, bytes(buf[i + 4:i + 4 + n]).decode("utf-8", "replace")):
                self._drop(conn)

    def _drop(self, conn):
        ctx = conn[4]
        if ctx is not None:                              # a file was open for this connection
            try:
                ctx[0].close()
            except (OSError, AttributeError):
                pass
            if conn[3] == 1:                             # an upload that did not finish: remove the partial file
                try:
                    os.remove(self.root + ctx[3] + ".new")
                except OSError:
                    pass
        try:
            conn[0].close()
        except OSError:
            pass
        if conn in self.conns:
            self.conns.remove(conn)

    def _json(self, conn, code, obj):
        data = json.dumps(obj).encode()
        self._send(conn[0], ("HTTP/1.0 %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nCache-Control: no-store\r\n"
                             "Connection: close\r\n\r\n" % (code, len(data))).encode() + data)
        return False

    def _answer(self, conn, method, path, hdr, body):
        """-> True when the connection stays open (a file is being sent)"""
        c = conn[0]
        if method == "GET" and path == "/":
            data = PAGE.encode()
            self._send(c, ("HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %d\r\n"
                           "Cache-Control: no-store\r\nConnection: close\r\n\r\n" % len(data)).encode() + data)
        elif method == "GET" and path == "/s":
            self._json(conn, "200 OK", self.state())
        elif method == "GET" and path == "/files":
            self._json(conn, "200 OK", self.files())
        elif method == "POST" and path == "/c":
            self._json(conn, "200 OK", self.command(body.split("\n")[0][:200], hdr))
        elif method == "GET" and path.startswith("/f/"):
            name = path[3:]
            try:
                if not _name_ok(name) or _ext(name) not in SERVED:
                    raise OSError
                size = os.stat(self.root + name)[6]
                f = open(self.root + name, "rb")
            except OSError:
                self._send(c, b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                return False
            conn[3] = 2
            conn[4] = [f, ("HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: %d\r\n"
                           "Connection: close\r\n\r\n" % size).encode()]
            return True
        else:
            self._send(c, b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        return False

    def _pump(self, conn):
        """a file on its way out: one piece per call, as much as the socket takes"""
        ctx = conn[4]
        if not ctx[1]:
            ctx[1] = ctx[0].read(1024)
            if not ctx[1]:
                return self._drop(conn)
        try:
            n = conn[0].send(ctx[1])
            ctx[1] = ctx[1][n:]
            conn[2] = 0
        except OSError:
            conn[2] += 1
            if conn[2] > 2000:
                self._drop(conn)

    # ---- a file coming in
    def _put(self, conn, name, hdr, n, first):
        why = self._pin_ok(hdr)
        if not why and (not _name_ok(name) or _ext(name) not in STORED):
            why = "only .py and .bit files with a plain name"
        if not why and not 0 < n <= MAX_UPLOAD:
            why = "length missing or over %d bytes" % MAX_UPLOAD
        if why:
            self._json(conn, "403 Forbidden", {"ok": False, "error": why})
            return self._drop(conn)
        try:
            f = open(self.root + name + ".new", "wb")
        except OSError as e:
            self._json(conn, "500 Error", {"ok": False, "error": "cannot write: %s" % e})
            return self._drop(conn)
        conn[3] = 1
        conn[4] = [f, n, 0, name, hdr.get("x-crc")]
        self._body(conn, first)

    def _body(self, conn, d):
        ctx = conn[4]
        d = d[:ctx[1]]
        try:
            if d:
                ctx[0].write(d)
                ctx[2] = crc32(d, ctx[2])
                ctx[1] -= len(d)
            if ctx[1]:
                return
            ctx[0].close()
            name, got = ctx[3], "%08x" % (ctx[2] & 0xFFFFFFFF)
            if ctx[4] is not None and ctx[4].lower() != got:
                raise ValueError("CRC %s, expected %s" % (got, ctx[4].lower()))
            try:
                os.remove(self.root + name)
            except OSError:
                pass
            os.rename(self.root + name + ".new", self.root + name)
            conn[3], conn[4] = 0, None
            self._json(conn, "200 OK", {"ok": True, "name": name, "crc": got})
        except (OSError, ValueError) as e:
            self._json(conn, "400 Bad Request", {"ok": False, "error": str(e)})
        self._drop(conn)

    @staticmethod
    def _send(c, data):
        try:
            c.settimeout(0.5)                            # a short wait at most: the sensors keep coming
            mv = memoryview(data)
            sent = 0
            while sent < len(data):
                sent += c.send(mv[sent:sent + 1460])
        except OSError:
            pass
