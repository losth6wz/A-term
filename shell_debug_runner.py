
import sys, os, pathlib, traceback

log = pathlib.Path('C:/Users/PC/A-term/shell_debug.txt')

try:
    sys.path.insert(0, r'C:\Users\PC\A-term')
    from shell import main
    log.write_text('About to call main()' + chr(10))
    main()
    log.write_text(log.read_text() + 'main() returned normally' + chr(10))
except SystemExit as e:
    log.write_text((log.read_text() if log.exists() else '') + f'SystemExit: {e}' + chr(10))
except Exception as e:
    log.write_text((log.read_text() if log.exists() else '') + f'Exception: {e}' + chr(10) + traceback.format_exc())
