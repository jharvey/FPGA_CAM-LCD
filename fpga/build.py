#!/usr/bin/env python3
"""Command-line build of the Icestudio project, without opening Icestudio.

    python fpga/build.py [--ice FILE] [--out DIR] [--gen-only] [--mem-mhz 87.5] [--seed N]

--mem-mhz 87.5 builds the fallback with a slower memory clock (SDRAM, capture, FIFOs, edge filter): 25 x 7 / 2 MHz
instead of 25 x 4, the SDRAM refresh count scaled to match.  Only the generated main.v changes; the .ice file stays.

Steps: run Icestudio's own code generator (compiler.js from the Icestudio install) on the
.ice file with the FCL board definition in fpga/icestudio/FCL, then yosys -> nextpnr-ecp5 ->
ecppack from the oss-cad-suite that Icestudio/apio installed. The generator needs a JavaScript
engine: `node` if it is on PATH, otherwise a headless Edge/Chrome/Chromium.

Environment overrides: ICESTUDIO_DIR (folder holding scripts/services/compiler.js),
OSS_CAD_SUITE (folder holding bin/yosys), BROWSER (browser executable).
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')

SHA1_JS = r"""
function sha1(msg){function rotl(n,s){return (n<<s)|(n>>>(32-s));}function hex(v){var s='';for(var i=7;i>=0;i--)s+=((v>>>(i*4))&15).toString(16);return s;}
var bytes=[];for(var i=0;i<msg.length;i++){var c=msg.charCodeAt(i);if(c<128)bytes.push(c);else if(c<2048){bytes.push(192|(c>>6),128|(c&63));}else{bytes.push(224|(c>>12),128|((c>>6)&63),128|(c&63));}}
var l=bytes.length;bytes.push(128);while(bytes.length%64!==56)bytes.push(0);var bl=l*8;bytes.push(0,0,0,0,(bl>>>24)&255,(bl>>>16)&255,(bl>>>8)&255,bl&255);
var h0=0x67452301,h1=0xEFCDAB89,h2=0x98BADCFE,h3=0x10325476,h4=0xC3D2E1F0;
for(var o=0;o<bytes.length;o+=64){var w=[];for(var j=0;j<16;j++)w[j]=(bytes[o+j*4]<<24)|(bytes[o+j*4+1]<<16)|(bytes[o+j*4+2]<<8)|bytes[o+j*4+3];
for(j=16;j<80;j++)w[j]=rotl(w[j-3]^w[j-8]^w[j-14]^w[j-16],1);var a=h0,b=h1,c2=h2,d=h3,e=h4;
for(j=0;j<80;j++){var f,k;if(j<20){f=(b&c2)|(~b&d);k=0x5A827999;}else if(j<40){f=b^c2^d;k=0x6ED9EBA1;}else if(j<60){f=(b&c2)|(b&d)|(c2&d);k=0x8F1BBCDC;}else{f=b^c2^d;k=0xCA62C1D6;}
var t=(rotl(a,5)+f+e+k+w[j])|0;e=d;d=c2;c2=rotl(b,30);b=a;a=t;}h0=(h0+a)|0;h1=(h1+b)|0;h2=(h2+c2)|0;h3=(h3+d)|0;h4=(h4+e)|0;}
return hex(h0)+hex(h1)+hex(h2)+hex(h3)+hex(h4);}
"""

# Same preparation Icestudio does before it calls the generator (services/graph.js, tools.js):
# board rules mark unconnected "clk" inputs so they are wired to the board clock.
PRE_JS = r"""
var svc = {};
var common = {selectedBoard: BOARD};
var utils = {clone: function(d){return JSON.parse(JSON.stringify(d));},
  digestId: function(id){if(id.indexOf('-')!==-1){id=sha1(id).toString();}return 'v'+id.substring(0,6);}};
var blocks = {BASIC_INPUT: 'basic.input', BASIC_OUTPUT: 'basic.output', BASIC_INPUT_LABEL: 'basic.inputLabel', BASIC_OUTPUT_LABEL: 'basic.outputLabel',
  BASIC_PAIRED_LABELS: 'basic.pairedLabel', BASIC_CODE: 'basic.code', BASIC_MEMORY: 'basic.memory', BASIC_CONSTANT: 'basic.constant', BASIC_INFO: 'basic.info'};
// The generator's dependency list differs between Icestudio versions, so hand them over by name.
var DEPS = {common: common, utils: utils, blocks: blocks, nodeSha1: sha1, _package: {version: VERSION}};
var angular = {module: function(){return {service: function(n, fn){
  var names = fn.toString().match(/function\s*\(([^)]*)\)/)[1].split(',').map(function(s){return s.trim();}).filter(function(s){return s;});
  names.forEach(function(d){if(!(d in DEPS)){throw new Error('Icestudio generator needs an unknown service: ' + d);}});
  fn.apply(svc, names.map(function(d){return DEPS[d];})); return this;}};}};
function rule(port, apply){var r=(BOARD.rules.input||[]);for(var i=0;i<r.length;i++){if(r[i].port===port){return {port:r[i].port,pin:r[i].pin,apply:apply};}}return undefined;}
function prepare(){
  var G = PROJECT.design.graph;
  function conn(bid, port){return G.wires.some(function(w){return w.target.block===bid && w.target.port===port;});}
  G.blocks.forEach(function(b){
    if (b.type === 'basic.code') {(b.data.ports.in||[]).forEach(function(pt){pt.default = rule(pt.name, !conn(b.id, pt.name));});}
    else if (b.type.indexOf('basic.') === -1) {var dep = PROJECT.dependencies[b.type]; var data = {ports:{in:[]}};
      dep.design.graph.blocks.forEach(function(it){if (it.type==='basic.input' && !it.data.range) {
        data.ports.in.push({name: it.id, default: rule((it.data.clock?'clk':'')||it.data.name, !conn(b.id, it.id))});}});
      b.data = data;}
  });
}
function generate(){
  prepare();
  var opt = {datetime: false, boardRules: true};
  opt.initPorts = svc.getInitPorts(PROJECT); opt.initPins = svc.getInitPins(PROJECT);
  var files = {};
  ['verilog','lpf','list'].forEach(function(t){svc.generate(t, PROJECT, opt).forEach(function(f){files[f.name]=f.content;});});
  return files;
}
"""


CLOCKS_MHZ = {'clk': 25.0, 'cmos_pclk': 24.0}       # input port name in the .ice file -> frequency


def find(paths, what):
    for p in paths:
        if p and os.path.exists(p):
            return p
    sys.exit('Cannot find %s. Looked in:\n  %s' % (what, '\n  '.join(str(p) for p in paths if p)))


def generate(ice, out, board_dir):
    icestudio = find([os.environ.get('ICESTUDIO_DIR'), r'C:\Program Files\icestudio', '/opt/icestudio',
                      os.path.join(HOME, 'icestudio')], 'Icestudio (set ICESTUDIO_DIR)')
    compiler = find([os.path.join(icestudio, 'scripts', 'services', 'compiler.js')], 'Icestudio compiler.js')
    version = '0.0.0'
    try:
        version = json.load(open(os.path.join(icestudio, 'package.json'), encoding='utf-8'))['version']
    except Exception:
        pass
    project = json.load(open(ice, encoding='utf-8'))
    board = {'name': project['design'].get('board', 'FCL')}
    for k in ('info', 'pinout', 'rules'):
        board[k] = json.load(open(os.path.join(board_dir, k + '.json'), encoding='utf-8'))
    known = {p['value'] for p in board['pinout']}
    for blk in project['design']['graph']['blocks']:
        d = blk.get('data') or {}
        if blk['type'] in ('basic.input', 'basic.output') and not d.get('virtual'):
            for p in d.get('pins') or []:
                if p['value'] not in known:
                    sys.exit('Pin %s of port %s is not in %s/pinout.json' % (p['value'], d.get('name'), board_dir))
    tmp = tempfile.mkdtemp(prefix='icegen_')
    data = 'var VERSION = %s;\nvar PROJECT = %s;\nvar BOARD = %s;\n' % (json.dumps(version), json.dumps(project), json.dumps(board))
    src = open(compiler, encoding='utf-8').read()
    node = shutil.which('node')
    if node:
        js = data + SHA1_JS + PRE_JS + src + '\nprocess.stdout.write(JSON.stringify(generate()));\n'
        open(os.path.join(tmp, 'gen.js'), 'w', encoding='utf-8').write(js)
        r = subprocess.run([node, os.path.join(tmp, 'gen.js')], capture_output=True, text=True, encoding='utf-8')
        if r.returncode:
            sys.exit('Code generation failed:\n' + r.stderr[-2000:])
        files = json.loads(r.stdout)
    else:
        browser = find([os.environ.get('BROWSER'),
                        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                        shutil.which('chromium'), shutil.which('chromium-browser'), shutil.which('google-chrome')],
                       'node or a Chromium-based browser (set BROWSER)')
        for name, text in (('data.js', data), ('compiler.js', src)):
            open(os.path.join(tmp, name), 'w', encoding='utf-8').write(text)
        page = ('<!doctype html><meta charset="utf-8"><pre id="out">PENDING</pre><script src="data.js"></script><script>'
                + SHA1_JS + PRE_JS + '</script><script src="compiler.js"></script><script>'
                'try{document.getElementById("out").textContent="RESULT"+btoa(unescape(encodeURIComponent(JSON.stringify(generate()))))+"END";}'
                'catch(e){document.getElementById("out").textContent="ERROR "+(e.stack||e);}</script>')
        open(os.path.join(tmp, 'page.html'), 'w', encoding='utf-8').write(page)
        url = 'file:///' + os.path.join(tmp, 'page.html').replace('\\', '/').lstrip('/')
        dom = subprocess.run([browser, '--headless', '--disable-gpu', '--no-sandbox',
                              '--user-data-dir=' + os.path.join(tmp, 'profile'),
                              '--allow-file-access-from-files', '--dump-dom', url],
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180).stdout
        m = re.search(r'RESULT([A-Za-z0-9+/=]+)END', dom)
        if not m:
            err = re.search(r'ERROR[^<]*', dom)
            sys.exit('Code generation failed:\n' + (err.group(0) if err else dom)[:2000])
        files = json.loads(base64.b64decode(m.group(1)).decode('utf-8'))
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    # Icestudio's pin file has no clock constraints, and nextpnr then checks every clock against 12 MHz only.
    # Give it the board clock (the PLL outputs follow from it) and the camera's pixel clock.
    extra = []
    for blk in project['design']['graph']['blocks']:
        d = blk.get('data') or {}
        mhz = CLOCKS_MHZ.get(d.get('name')) if blk['type'] == 'basic.input' else None
        if mhz:
            port = 'v' + (hashlib.sha1(blk['id'].encode()).hexdigest() if '-' in blk['id'] else blk['id'])[:6]
            extra.append('FREQUENCY PORT "%s" %g MHZ;  # %s' % (port, mhz, d['name']))
    for name in files:
        if name.endswith('.lpf') and extra:
            files[name] = files[name].rstrip('\n') + '\n\n# -- clocks (added by fpga/build.py)\n' + '\n'.join(extra) + '\n'
    for name, content in files.items():
        open(os.path.join(out, name), 'w', encoding='utf-8', newline='\n').write(content)
    print('generated:', ', '.join(sorted(files)))


# the memory clock's PLL and the refresh count that goes with it (fpga/IO_REMAP.md, section Clocks)
MEM_CLOCKS = {100.0: ('"100"', 1, 4, 750), 87.5: ('"87.5"', 2, 7, 656)}


def mem_clock(out, mhz):
    """rewrite the generated main.v for another memory clock: PLL dividers, its frequency attribute, refresh count"""
    if mhz == 100.0:
        return
    path = os.path.join(out, 'main.v')
    v = open(path, encoding='utf-8').read()
    a, b = MEM_CLOCKS[100.0], MEM_CLOCKS[mhz]
    for old, new in (('FREQUENCY_PIN_CLKOP=%s' % a[0], 'FREQUENCY_PIN_CLKOP=%s' % b[0]),
                     ('.CLKI_DIV(%d),' % a[1], '.CLKI_DIV(%d),' % b[1]),
                     ('.CLKFB_DIV(%d)' % a[2], '.CLKFB_DIV(%d)' % b[2]),
                     ('refresh_ctr_q==%d' % a[3], 'refresh_ctr_q==%d' % b[3])):
        if v.count(old) != 1:
            sys.exit('main.v: "%s" found %d times, expected once: the memory clock block has changed' % (old, v.count(old)))
        v = v.replace(old, new)
    open(path, 'w', encoding='utf-8', newline='\n').write(v)
    print('memory clock set to %g MHz in main.v' % mhz)


def run(cmd, cwd, env):
    print('>', ' '.join(cmd))
    sys.stdout.flush()
    # Windows looks the program up on the parent's PATH, not env's, so resolve it here
    cmd = [shutil.which(cmd[0], path=env['PATH']) or cmd[0]] + cmd[1:]
    r = subprocess.run(cmd, cwd=cwd, env=env)
    if r.returncode:
        sys.exit('%s failed (exit %d); see the log in %s' % (cmd[0], r.returncode, cwd))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ice', default=os.path.join(HERE, 'CameraToTFTSobel_FCL.ice'))
    ap.add_argument('--out', default=os.path.join(HERE, 'build'))
    ap.add_argument('--board', default=os.path.join(HERE, 'icestudio', 'FCL'))
    ap.add_argument('--gen-only', action='store_true', help='stop after writing main.v and main.lpf')
    ap.add_argument('--mem-mhz', type=float, default=100.0, choices=sorted(MEM_CLOCKS), help='memory clock (default 100)')
    ap.add_argument('--seed', type=int, default=1, help='nextpnr placement seed (default 1)')
    a = ap.parse_args()
    generate(a.ice, a.out, a.board)
    mem_clock(a.out, a.mem_mhz)
    if a.gen_only:
        return
    env = dict(os.environ)
    suite = os.environ.get('OSS_CAD_SUITE') or os.path.join(HOME, '.icestudio', 'apio', 'packages', 'tools-oss-cad-suite')
    if os.path.isdir(suite):
        env['PATH'] = os.pathsep.join([os.path.join(suite, 'bin'), os.path.join(suite, 'lib'), env['PATH']])
    for tool in ('yosys', 'nextpnr-ecp5', 'ecppack'):
        if not shutil.which(tool, path=env['PATH']):
            sys.exit('Cannot find %s (set OSS_CAD_SUITE to an oss-cad-suite folder)' % tool)
    run(['yosys', '-q', '-l', 'yosys.log', '-p', 'read_verilog main.v; synth_ecp5 -top main -json main.json'], a.out, env)
    run(['nextpnr-ecp5', '--85k', '--package', 'CABGA381', '--json', 'main.json', '--lpf', 'main.lpf',
         '--textcfg', 'main.config', '--seed', str(a.seed), '--timing-allow-fail', '-q', '-l', 'nextpnr.log'], a.out, env)
    run(['ecppack', '--compress', 'main.config', 'main.bit'], a.out, env)
    last = {}
    for line in open(os.path.join(a.out, 'nextpnr.log'), encoding='utf-8', errors='replace'):
        m = re.search(r"Max frequency for clock\s+'([^']+)': ([\d.]+) MHz \((PASS|FAIL) at ([\d.]+) MHz\)", line)
        if m:
            last[m.group(1)] = m.groups()[1:]
        elif re.search(r'TRELLIS_(IO|COMB|FF):', line):
            print(line.rstrip())
    for clk, (mhz, res, want) in sorted(last.items()):         # the figures after routing
        print('clock %-40s %7s MHz possible, %s at %s MHz' % (clk[-40:], mhz, res, want))
    print('bitstream:', os.path.join(a.out, 'main.bit'))


if __name__ == '__main__':
    main()
