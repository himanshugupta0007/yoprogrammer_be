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
    code = str(body.get("code", "")).strip()
    new_password = str(body.get("newPassword", ""))

    if not email or not _EMAIL_RE.match(email):
        return _res(400, {"message": "Invalid email address"})
    if not code:
        return _res(400, {"message": "Reset code is required"})
    if len(new_password) < 8:
        return _res(400, {"message": "Password must be at least 8 characters"})

    logger.info("Reset password attempt", email=email)

    try:
        cognito.confirm_forgot_password(
            ClientId=config["user_pool_client_id"],
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )
        logger.info("Password reset successful", email=email)
        return _res(200, {"message": "Password reset successful. You can now sign in."})
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "CodeMismatchException":
            return _res(400, {"message": "Invalid reset code."})
        if error_code == "ExpiredCodeException":
            return _res(400, {"message": "Reset code has expired. Please request a new one."})
        if error_code == "InvalidPasswordException":
            return _res(400, {"message": e.response["Error"]["Message"]})
        logger.error("Reset password failed", email=email, error=str(e))
        raise
