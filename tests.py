import os, sys

for _ in (f for f in os.listdir("libs") if f.endswith(".awfl")):
  print(_); os.system(sys.executable + " awfl.py " + _ + " ".join(sys.argv[1:]))
