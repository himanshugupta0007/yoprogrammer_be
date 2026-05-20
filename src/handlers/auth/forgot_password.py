import json
import re

import boto3
from botocore.exceptions import ClientError

from src.shared.config import config
from src.shared.powertools import logger, tracer

cognito = boto3.client("cognito-idp")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _res(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _res(400, {"message": "Invalid JSON body"})

    email = str(body.get("email", "")).strip()

    if not email or not _EMAIL_RE.match(email):
        return _res(400, {"message": "Invalid email address"})

    logger.info("Forgot password request", email=email)

    try:
        cognito.forgot_password(
            ClientId=config["user_pool_client_id"],
            Username=email,
        )
        return _res(200, {"message": "Password reset code sent to your email."})
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "UserNotFoundException":
            return _res(200, {"message": "Password reset code sent to your email."})
        logger.error("Forgot password failed", email=email, error=str(e))
        raise
