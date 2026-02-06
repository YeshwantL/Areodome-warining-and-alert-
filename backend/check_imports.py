import sys
import os

print(f"CWD: {os.getcwd()}")
# Simulate expected Docker PYTHONPATH
# 1. Root (for routers)
# 2. app/ (for database, tasks etc. - automatic if running app/main.py?)
# 3. app/database (for models)

sys.path.insert(0, os.getcwd()) # Root
sys.path.insert(0, os.path.join(os.getcwd(), 'app')) # App
sys.path.insert(0, os.path.join(os.getcwd(), 'app', 'database')) # Models location

print(f"Path: {sys.path}")

try:
    import models
    print(f"SUCCESS: 'import models' worked. File: {models.__file__}")
except ImportError as e:
    print(f"FAILURE: 'import models' failed: {e}")

try:
    from routers import authentication
    print(f"SUCCESS: 'from routers import authentication' worked. File: {authentication.__file__}")
except ImportError as e:
    print(f"FAILURE: 'from routers import authentication' failed: {e}")
