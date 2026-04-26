import winpty, sys, os, time, threading, queue

cmd = [sys.executable, os.path.join(os.getcwd(), "main.py"), "--aterm-shell"]
proc = winpty.PtyProcess.spawn(cmd, dimensions=(24, 80))

data_q = queue.Queue()

WINPTY_DISABLE = {
    "\x1b[?9001h": "\x1b[?9001l",
    "\x1b[?1004h": "\x1b[?1004l",
}

def reader():
    while True:
        try:
            d = proc.read(4096)
            for seq, resp in WINPTY_DISABLE.items():
                if seq in d:
                    proc.write(resp)
                    data_q.put(f"[disabled: {repr(seq)}]")
            data_q.put(("data", d))
        except:
            break

t = threading.Thread(target=reader, daemon=True)
t.start()

# Collect output for 2 seconds
all_text = ""
deadline = time.time() + 2.0
while time.time() < deadline:
    try:
        item = data_q.get(timeout=0.1)
        if isinstance(item, tuple) and item[0] == "data":
            all_text += item[1]
        else:
            print(item)
    except queue.Empty:
        pass

print("got banner:", "A-term" in all_text or "_" in all_text)
print("alive:", proc.isalive())

# Send a command
proc.write("echo HELLO_WORKS\r")
print("sent: echo HELLO_WORKS")

# Collect response for 2 seconds
resp_text = ""
deadline = time.time() + 2.0
while time.time() < deadline:
    try:
        item = data_q.get(timeout=0.1)
        if isinstance(item, tuple) and item[0] == "data":
            resp_text += item[1]
    except queue.Empty:
        pass

proc.terminate()
print("response has HELLO_WORKS:", "HELLO_WORKS" in resp_text)
print("resp:", repr(resp_text[:200]))
