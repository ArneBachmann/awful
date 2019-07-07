import os, sys

for _ in (f for f in os.listdir("libs") if f not in ("standard.awfl", "io.awfl", "maths.awfl")):
  print(_)
  os.system(sys.executable + " awfl.py " + _)
