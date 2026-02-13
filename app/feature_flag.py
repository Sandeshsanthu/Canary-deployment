import os
from UnleashClient import UnleashClient

_unleash_client = None

def init_unleash():
    global _unleash_client
    if _unleash_client is None:
        unleash_url = os.environ.get("UNLEASH_URL", "http://localhost:4242/api/")
        unleash_app = os.environ.get("UNLEASH_APP_NAME", "dark-feature")
        unleash_token = os.environ.get("UNLEASH_API_TOKEN", "default:development.03b0f6bd576cb3ff4daa390b0d7d85b11596d15bb64c6e4ed0e85065")

        _unleash_client = UnleashClient(
            url=unleash_url,
            app_name=unleash_app,
            custom_headers={"Authorization": unleash_token},
        )
        _unleash_client.initialize_client()
    return _unleash_client

def shutdown_unleash():
    global _unleash_client
    if _unleash_client is not None:
        try:
            _unleash_client.destroy()
        finally:
            _unleash_client = None

def is_enabled(flag_name: str, default: bool = False, context: dict | None = None) -> bool:
    client = init_unleash()
    return client.is_enabled(flag_name, context=context, fallback_function=lambda _name, _ctx: default)
