"""Talk to MicroPython running in the ESP32 emulator (its UART0 on a TCP port) through the raw REPL, in raw-paste
mode, whose flow control keeps the emulated UART from dropping bytes.  Used by test_esp32_qemu.py.

    python3 esp_raw.py probe                       boot messages and a version line
    python3 esp_raw.py put <local> <remote> ...    copy files
    python3 esp_raw.py run <file.py> [seconds]     run a local file's code on the board, print what it prints
"""
import socket
import sys
import time

PORT = 5555


class Board:
    def __init__(self, port=PORT, wait=30.0):
        end = time.time() + wait
        while True:
            try:
                self.s = socket.create_connection(("127.0.0.1", port))
                break
            except OSError:
                if time.time() > end:
                    raise
                time.sleep(0.5)
        self.s.settimeout(0.2)
        self.buf = b""

    def _fill(self, wait):
        """take what has arrived; wait up to `wait` seconds for something"""
        self.s.settimeout(wait if wait > 0 else 0.001)
        try:
            d = self.s.recv(65536)
            if d:
                self.buf += d
        except (socket.timeout, BlockingIOError):
            pass

    def read(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self._fill(0.2)
        out, self.buf = self.buf, b""
        return out

    def read_until(self, token, timeout):
        end = time.time() + timeout
        while token not in self.buf:
            if time.time() > end:
                raise TimeoutError("waited %.0f s for %r; got %r" % (timeout, token, self.buf[-300:]))
            self._fill(0.2)
        i = self.buf.index(token) + len(token)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def read_n(self, n, timeout=10):
        end = time.time() + timeout
        while len(self.buf) < n:
            if time.time() > end:
                raise TimeoutError("waited for %d bytes; got %r" % (n, self.buf))
            self._fill(0.2)
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def raw(self):
        self.s.sendall(b"\r\x03\x03")
        time.sleep(0.3)
        self.read(0.3)
        self.s.sendall(b"\r\x01")
        self.read_until(b"raw REPL; CTRL-B to exit\r\n>", 10)

    def exec(self, code, timeout=60):
        """run code on the board -> (output, error output)"""
        if isinstance(code, str):
            code = code.encode()
        self.s.sendall(b"\x05A\x01")
        if self.read_n(2) != b"R\x01":
            raise RuntimeError("the board has no raw-paste mode")
        w = self.read_n(2)
        win = w[0] | w[1] << 8
        left, i = win, 0
        while i < len(code):
            self._fill(0.5 if left == 0 else 0)           # flow control: 0x01 = room for one more window
            while self.buf:
                c, self.buf = self.buf[:1], self.buf[1:]
                if c == b"\x01":
                    left += win
                elif c == b"\x04":
                    raise RuntimeError("the board stopped the upload")
            if left == 0:
                continue
            n = min(left, len(code) - i)
            self.s.sendall(code[i:i + n])
            i += n
            left -= n
        self.s.sendall(b"\x04")
        self.read_until(b"\x04", 30)                       # the board has all of it and compiles it
        out = self.read_until(b"\x04", timeout)[:-1]
        err = self.read_until(b"\x04", 30)[:-1]
        self.read_until(b">", 30)
        return out.decode(errors="replace"), err.decode(errors="replace")

    def put(self, local, remote):
        data = open(local, "rb").read()
        out, err = self.exec("f=open(%r,'wb')" % remote)
        if err:
            raise RuntimeError(err)
        for i in range(0, len(data), 2048):
            out, err = self.exec("f.write(%r)" % data[i:i + 2048])
            if err:
                raise RuntimeError(err)
        self.exec("f.close()")
        out, err = self.exec("import os\nprint(os.stat(%r)[6])" % remote)
        if out.strip() != str(len(data)):
            raise RuntimeError("%s: %s bytes on the board, %d here" % (remote, out.strip(), len(data)))

    def mkdir(self, path):
        self.exec("import os\ntry:\n os.mkdir(%r)\nexcept OSError:\n pass" % path)


if __name__ == "__main__":
    b = Board()
    if sys.argv[1] == "probe":
        b.s.sendall(b"\r")
        print(b.read(3).decode(errors="replace")[-500:])
        b.raw()
        print(b.exec("import sys, gc\nprint(sys.version, sys.platform, sys.implementation._machine)\nprint('heap', gc.mem_free())"))
    elif sys.argv[1] == "put":
        b.raw()
        args = sys.argv[2:]
        for local, remote in zip(args[0::2], args[1::2]):
            if "/" in remote.strip("/"):
                b.mkdir(remote.rsplit("/", 1)[0])
            b.put(local, remote)
        print("copied", len(args) // 2, "files")
    elif sys.argv[1] == "run":
        b.raw()
        out, err = b.exec(open(sys.argv[2]).read(), float(sys.argv[3]) if len(sys.argv) > 3 else 600)
        sys.stdout.write(out)
        if err:
            sys.stdout.write("ERROR " + err)
