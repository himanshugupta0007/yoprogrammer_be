import json
import os

import boto3
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer
from src.shared.tags import serialize_tags

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

    snippet_id = (event.get("pathParameters") or {}).get("snippetId", "").strip()
    if not snippet_id:
        return _res(400, {"message": "snippetId is required"})

    logger.info("Getting snippet", userId=user_id, snippetId=snippet_id)

    try:
        result = table.get_item(Key={"userId": user_id, "snippetId": snippet_id})
    except ClientError as e:
        logger.error("Failed to get snippet", userId=user_id, snippetId=snippet_id, error=str(e))
        raise

    item = result.get("Item")
    if not item or item.get("isDeleted"):
        return _res(404, {"message": "Snippet not found"})

    return _res(200, {**item, "tags": serialize_tags(item.get("tags", []))})
