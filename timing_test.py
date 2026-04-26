import sys, time, pathlib

log = pathlib.Path("C:/Users/PC/A-term/timing_debug.txt")

def w(msg):
    log.open("a").write(f"{time.time():.3f}: {msg}\n")

w("subprocess started")
w(f"argv={sys.argv}")

try:
    w("importing aterm_cmd")
    import aterm_cmd
    w("importing plugins")
    import plugins
    w("importing config")
    from config import CFG
    w(f"config loaded, banner={CFG.shell_banner}")
    w("calling shell.main")
    from shell import main
    main()
except Exception as e:
    import traceback
    w(f"EXCEPTION: {e}")
    w(traceback.format_exc())
