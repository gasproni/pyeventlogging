import os
import sys

source_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if not sys.path[0] == source_path:
    sys.path.insert(0, source_path)
