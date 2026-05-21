"""Utilities for loading service FastAPI apps in isolation during tests.

Each Aegis Hub service lives under aegis-hub-code/<service>/ and uses a
package named `app`.  Loading all three in the same Python process would
create module-name conflicts.  This helper:

  1. Clears any previously loaded app.* modules from sys.modules.
  2. Temporarily inserts the service directory into sys.path.
  3. Imports app.main and captures references to every app.* module.
  4. Removes the service directory from sys.path.

Callers store the returned module-reference dict and later use
`unittest.mock.patch.object(module_ref, "func_name")` for mocking.
Using patch.object with the captured reference works regardless of what
sys.modules contains at test time, avoiding cross-service interference.
"""
import importlib
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent


def load_service_app(
    service_dir_name: str,
    env_vars: dict[str, str],
) -> tuple[Any, dict[str, Any]]:
    """Load a service's FastAPI app in isolation.

    Args:
        service_dir_name: Sub-directory name under aegis-hub-code/
                          (e.g. "slack-gateway", "query-processor").
        env_vars: Environment variables required by the service's Settings.

    Returns:
        (app, modules) where modules maps strings like
        "app.integrations.slack_web_api" to the actual module objects.
    """
    service_dir = str(ROOT / "aegis-hub-code" / service_dir_name)

    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]

    os.environ.update(env_vars)
    sys.path.insert(0, service_dir)

    try:
        app_main = importlib.import_module("app.main")
        app = app_main.app
        modules: dict[str, Any] = {
            key: mod
            for key, mod in sys.modules.items()
            if key == "app" or key.startswith("app.")
        }
    finally:
        if service_dir in sys.path:
            sys.path.remove(service_dir)

    config_mod = modules.get("app.config")
    if config_mod and hasattr(config_mod, "get_settings"):
        config_mod.get_settings.cache_clear()

    return app, modules
