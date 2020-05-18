import os, sys

libs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs")

for _ in (f for f in os.listdir(libs) if f.endswith(".awfl")):
  print(_); os.system("awful %s/%s %s" % (libs, _, " ".join(sys.argv[1:])))
