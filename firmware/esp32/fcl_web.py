# The unit as a web page over Wi-Fi: the LCD text, the readings, and buttons for the everyday commands.
# Runs on the ESP32 (MicroPython, started by fcl_usbdev.py on port 80) and on a PC (python fcl_sim.py --web 8080).
#
#   web = Web(usb, hub, plat, port=80)      usb: fcl_usb.Bridge
#   web.poll()                              call from the main loop; never waits for a slow client
#
#   GET /       the page (one file, no outside scripts, works without internet)
#   GET /s      state as JSON: telemetry, LCD rows, Wi-Fi, compass calibration, servos
#   POST /c     one command line of fcl_usb.py in the body -> {"ok": true, "lines": [...]}
#
# No password: anyone on the same network can press these buttons.  So only the commands in ALLOWED are taken
# here; Wi-Fi settings, calibration values, audio and the Python prompt stay on the USB port.
import json
import socket

ALLOWED = ("key", "mode", "view", "threshold", "overlay", "zero", "follow", "servo", "pan", "magcal", "log", "tone", "status")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FCL monocular</title><style>
:root{--bg:#f4f5f2;--card:#fff;--ink:#1c2321;--dim:#66706c;--line:#d9ddd7;--acc:#0a7d5a;--warn:#b25c00;--bad:#b3261e}
@media(prefers-color-scheme:dark){:root{--bg:#121514;--card:#1c2120;--ink:#e8ece9;--dim:#98a39e;--line:#2c3331;--acc:#4fd1a1;--warn:#f0a94a;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 system-ui,sans-serif}
main{max-width:460px;margin:0 auto;padding:12px 16px 32px}h1{font-size:17px;margin:4px 0 10px;display:flex;justify-content:space-between}
#link{font-weight:400;color:var(--dim);font-size:14px}#link.bad{color:var(--bad)}
svg{display:block;width:100%;max-width:340px;margin:0 auto 12px}
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
<g id="dot"><circle r="13" fill="#000"/><circle r="9.5" fill="none" stroke-width="3"/><circle r="3"/></g></svg>
<div class="g">
<div class="c"><small>Heading</small><b id="hd">-</b> <span id="card"></span></div>
<div class="c"><small>Pitch / roll</small><b id="pr">-</b></div>
<div class="c"><small>Height</small><b id="alt">-</b> <span id="hpa"></span></div>
<div class="c"><small>Distance</small><b id="dist">-</b></div>
<div class="c w"><small>Cells</small><div class="cell" id="cells"></div></div>
<div class="c w"><small>Status</small><span id="st">-</span></div>
</div>
<div class="k">
<button data-c="key B1">B1 page</button><button data-c="key B2">B2 action</button><button data-c="key B1L">Menu</button>
<button id="view">View</button><button data-c="zero">Zero height</button><button id="foll">Level servo</button>
<button id="ovl">Overlay</button><button id="log">Log</button><button id="pan">Pan hold</button>
</div><div id="msg"></div></main><script>
var S=null,C=["N","NE","E","SE","S","SW","W","NW"],$=function(i){return document.getElementById(i)};
function send(c){fetch("/c",{method:"POST",body:c}).then(function(r){return r.json()}).then(function(j){
$("msg").textContent=c+": "+(j.lines.length?j.lines[j.lines.length-1].replace(/^\\$R,/,""):"")}).catch(function(){$("msg").textContent=c+": no answer"})}
document.querySelectorAll("button[data-c]").forEach(function(b){b.onclick=function(){send(b.dataset.c)}});
$("view").onclick=function(){send("view "+(S&&S.edges?"camera":"edges"))};
$("foll").onclick=function(){send("follow "+(S&&S.follow?"off":"on"))};
$("ovl").onclick=function(){var m=S?S.t.overlay:63;send("overlay "+(m==63?1:m==1?0:63))};
$("log").onclick=function(){send("log "+(S&&S.log?"off":"on"))};
$("pan").onclick=function(){send("pan "+(S&&S.pan!=null?"off":"here"))};
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
$("ovl").textContent="Overlay: "+(t.overlay==63?"all":t.overlay==1?"dot":t.overlay==0?"off":"custom")}
function tick(){fetch("/s").then(function(r){return r.json()}).then(function(s){$("link").textContent="live";$("link").className="";if(s.t&&s.t.heading!=null)show(s)})
.catch(function(){$("link").textContent="no connection";$("link").className="bad"}).then(function(){setTimeout(tick,300)})}
tick();</script></body></html>
"""


class Web:
    def __init__(self, usb, hub, plat=None, port=80):
        self.usb, self.hub, self.plat = usb, hub, plat
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(socket.getaddrinfo("0.0.0.0", port)[0][-1])
        s.listen(2)
        s.setblocking(False)
        self.s = s
        self.port = port
        self.conns = []                  # [socket, bytearray received, polls waited]
        self.requests = 0

    def close(self):
        for c in self.conns:
            c[0].close()
        self.conns = []
        self.s.close()

    # ---- what the page shows
    def state(self):
        hub = self.hub
        f = getattr(self.plat, "wifi_status", None)
        apps = hub.apps
        app = apps.pages[hub.mode_n] if hub.mode_n < len(apps.pages) else None
        return {"t": hub.last, "lcd": hub.osd, "page": "OVERVIEW" if app is None else app.name, "menu": apps.menu_open,
                "wifi": list(f()) if f else ["off", "", "", 0], "mag": hub.cal.status(), "servos": self.usb.servos,
                "log": apps.log_on, "edges": hub.edges, "follow": hub.follow_on, "pan": hub.pan_target}

    def command(self, line):
        a = line.strip().split()
        if not a or a[0].lower() not in ALLOWED:
            return {"ok": False, "lines": ["$R,err,not available on the web page: " + (a[0] if a else "")]}
        usb = self.usb
        usb.capture = []
        try:
            usb.command(line)
            lines = usb.capture
        finally:
            usb.capture = None
        return {"ok": bool(lines) and lines[-1].startswith("$R,ok"), "lines": lines}

    # ---- sockets
    def poll(self):
        try:
            c, _ = self.s.accept()
            c.setblocking(False)
            if len(self.conns) >= 4:
                self.conns.pop(0)[0].close()
            self.conns.append([c, bytearray(), 0])
        except OSError:
            pass
        for conn in self.conns[:]:
            c, buf = conn[0], conn[1]
            try:
                d = c.recv(1024)
            except OSError:
                conn[2] += 1
                if conn[2] > 2000:                       # a client that never finishes its request
                    self._drop(conn)
                continue
            if not d:
                self._drop(conn)
                continue
            buf.extend(d)
            i = bytes(buf).find(b"\r\n\r\n")
            if i < 0:
                if len(buf) > 2048:
                    self._drop(conn)
                continue
            head = bytes(buf[:i]).decode("utf-8", "replace")
            n = 0
            for h in head.split("\r\n")[1:]:
                if h.lower().startswith("content-length:"):
                    n = int(h.split(":")[1])
            if len(buf) < i + 4 + n:
                continue
            self._answer(c, head.split(" "), bytes(buf[i + 4:i + 4 + n]).decode("utf-8", "replace"))
            self._drop(conn)

    def _drop(self, conn):
        try:
            conn[0].close()
        except OSError:
            pass
        if conn in self.conns:
            self.conns.remove(conn)

    def _answer(self, c, req, body):
        self.requests += 1
        method, path = req[0], req[1] if len(req) > 1 else "/"
        if method == "GET" and path == "/":
            typ, out = "text/html; charset=utf-8", PAGE
        elif method == "GET" and path == "/s":
            typ, out = "application/json", json.dumps(self.state())
        elif method == "POST" and path == "/c":
            typ, out = "application/json", json.dumps(self.command(body.split("\n")[0][:200]))
        else:
            return self._send(c, b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        data = out.encode()
        self._send(c, ("HTTP/1.0 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nCache-Control: no-store\r\n"
                       "Connection: close\r\n\r\n" % (typ, len(data))).encode() + data)

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
