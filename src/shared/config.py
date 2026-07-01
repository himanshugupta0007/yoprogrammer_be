import os


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


config = {
    "user_pool_client_id": _require("USER_POOL_CLIENT_ID"),
    "user_pool_id": _require("USER_POOL_ID"),
    "stage": _require("STAGE"),
}
