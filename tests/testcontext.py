import os
import sys

sourcepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if not sys.path[0] == sourcepath:
    sys.path.insert(0, sourcepath)
