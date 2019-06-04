import os, sys

for _ in ("standard.awfl", "io.awfl", "maths.awfl"): print(_); os.system(sys.executable + " awfl.py " + _)
