"""
Configuration for the vulnmgmt pipeline.

Everything here comes from environment variables so credentials never
land in the repo. Set these before running main.py, e.g.:

    export GVM_SOCKET_PATH=/home/labuntuadmin/gvm-stack/sockets/gvmd/gvmd.sock
    export GVM_USERNAME=admin
    export GVM_PASSWORD=admin   # or whatever you've actually set it to

DB_PATH defaults to a local file so the tool runs out of the box for
testing, but override it if you want the tracker DB somewhere durable.
"""

import os

GVM_SOCKET_PATH = os.environ.get("GVM_SOCKET_PATH", "/run/gvmd/gvmd.sock")
GVM_USERNAME = os.environ.get("GVM_USERNAME")
GVM_PASSWORD = os.environ.get("GVM_PASSWORD")

DB_PATH = os.environ.get("VULNMGMT_DB_PATH", "vulnmgmt.db")

if __name__ == "__main__":
    missing = [name for name, val in
               [("GVM_USERNAME", GVM_USERNAME), ("GVM_PASSWORD", GVM_PASSWORD)]
               if not val]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
    else:
        print("Config looks complete.")
