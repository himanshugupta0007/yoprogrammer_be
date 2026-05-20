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
    password = str(body.get("password", ""))

    if not email or not _EMAIL_RE.match(email):
        return _res(400, {"message": "Invalid email address"})
    if not password:
        return _res(400, {"message": "Password is required"})

    logger.info("Sign in attempt", email=email)

    try:
        response = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=config["user_pool_client_id"],
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        result = response["AuthenticationResult"]
        logger.info("Sign in successful", email=email)
        return _res(200, {
            "idToken": result["IdToken"],
            "accessToken": result["AccessToken"],
            "refreshToken": result["RefreshToken"],
            "expiresIn": result["ExpiresIn"],
        })
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NotAuthorizedException":
            return _res(401, {"message": "Incorrect email or password."})
        if error_code == "UserNotConfirmedException":
            return _res(403, {"message": "Email not confirmed. Please verify your account first."})
        logger.error("Sign in failed", email=email, error=str(e))
        raise
