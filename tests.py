import os, sys

for _ in ("maps.awfl", "maths.awfl", "sets.awfl", "strings.awfl", "types.awfl"):
  print(_)
  os.system(sys.executable + " awfl.py " + _)
