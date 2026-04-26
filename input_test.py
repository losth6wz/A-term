import winpty, sys, os, time

cmd = [sys.executable, os.path.join(os.getcwd(), "main.py"), "--aterm-shell"]
proc = winpty.PtyProcess.spawn(cmd, dimensions=(24, 80))

# Let shell start up and send its init sequences
time.sleep(1.5)

# Read and process init data (disable Win32 input mode)
all_data = ""
for _ in range(10):
    try:
        d = proc.read(4096)
        all_data += d
        # Disable Win32 input mode
        if "\x1b[?9001h" in d:
            proc.write("\x1b[?9001l")
            print("disabled Win32 input mode")
        if "\x1b[?1004h" in d:
            proc.write("\x1b[?1004l")
    except:
        break
    if not proc.isalive():
        break

print("got data:", len(all_data), "chars")
print("alive:", proc.isalive())

# Now type a command
time.sleep(0.3)
proc.write("echo hello_from_test\r")
time.sleep(1.5)

# Read response
resp = ""
for _ in range(10):
    try:
        d = proc.read(4096)
        resp += d
    except:
        break

proc.terminate()
print("response contains 'hello_from_test':", "hello_from_test" in resp)
print("resp:", repr(resp[:300]))
