
import sys, os, time

with open('C:/Users/PC/A-term/pty_debug.txt', 'w') as f:
    f.write('started' + chr(10))
    f.write('stdin_none=' + str(sys.stdin is None) + chr(10))
    f.write('argv=' + str(sys.argv) + chr(10))
