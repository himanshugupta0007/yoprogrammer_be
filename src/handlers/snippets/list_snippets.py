import json
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SNIPPETS_TABLE_NAME"])


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
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return _res(401, {"message": "Unauthorized"})

    logger.info("Listing snippets", userId=user_id)

    try:
        result = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        items = result.get("Items", [])
        logger.info("Snippets listed", userId=user_id, count=len(items))
        return _res(200, {"snippets": items, "count": len(items)})
    except ClientError as e:
        logger.error("Failed to list snippets", userId=user_id, error=str(e))
        raise
