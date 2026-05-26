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
@tracer.capture_lambda_handler(capture_response=False)
def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _res(400, {"message": "Invalid JSON body"})

    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    name = str(body.get("name", "")).strip()

    if not email or not _EMAIL_RE.match(email):
        return _res(400, {"message": "Invalid email address"})
    if len(password) < 8:
        return _res(400, {"message": "Password must be at least 8 characters"})

    logger.info("Sign up attempt", email=email)

    user_attributes = [{"Name": "email", "Value": email}]
    if name:
        user_attributes.append({"Name": "name", "Value": name})

    try:
        cognito.sign_up(
            ClientId=config["user_pool_client_id"],
            Username=email,
            Password=password,
            UserAttributes=user_attributes,
        )
        logger.info("Sign up successful", email=email)
        return _res(200, {"message": "Sign up successful. Check your email for a verification code."})
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "UsernameExistsException":
            return _res(409, {"message": "An account with this email already exists."})
        if error_code == "InvalidPasswordException":
            return _res(400, {"message": e.response["Error"]["Message"]})
        logger.error("Sign up failed", email=email, error=str(e))
        raise
