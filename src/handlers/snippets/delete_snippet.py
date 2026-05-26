import json
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SNIPPETS_TABLE_NAME"])


def _res(status_code: int, body: dict = None) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
        "body": json.dumps(body or {}),
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

    logger.info("Deleting snippet", userId=user_id, snippetId=snippet_id)

    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        table.update_item(
            Key={"userId": user_id, "snippetId": snippet_id},
            UpdateExpression="SET isDeleted = :flag, deletedAt = :ts",
            ConditionExpression=Attr("snippetId").exists() & Attr("isDeleted").not_exists(),
            ExpressionAttributeValues={":flag": True, ":ts": deleted_at},
        )
        logger.info("Snippet deleted", userId=user_id, snippetId=snippet_id)
        return _res(204)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _res(404, {"message": "Snippet not found"})
        logger.error("Failed to delete snippet", userId=user_id, snippetId=snippet_id, error=str(e))
        raise
