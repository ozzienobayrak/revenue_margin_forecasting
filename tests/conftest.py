# Lets the tests import the modules in src/ (e.g. "import config")
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
