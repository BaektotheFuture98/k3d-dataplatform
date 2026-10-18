import os

c = get_config()  # noqa: F821: loaded by Jupyter
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.root_dir = "/workspace"
c.IdentityProvider.token = os.environ["JUPYTER_TOKEN"]
if not c.IdentityProvider.token:
    raise ValueError("JUPYTER_TOKEN must be nonempty")
# Startup URLs contain the token; omit them from shared Pod logs.
c.ServerApp.log_level = "WARN"
