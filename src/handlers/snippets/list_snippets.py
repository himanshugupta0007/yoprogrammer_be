import json
import os

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer
from src.shared.tags import VALID_TAG_TYPES, serialize_tags

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

    params = event.get("queryStringParameters") or {}
    tag_filter = params.get("tag", "").strip().lower()

    filter_expr = Attr("isDeleted").not_exists()

    if tag_filter:
        if ":" in tag_filter:
            # exact type:value search, e.g. ?tag=project:yoprogrammer
            tag_expr = Attr("tags").contains(tag_filter)
        else:
            # value-only search — match across all tag types
            tag_expr = None
            for tag_type in VALID_TAG_TYPES:
                cond = Attr("tags").contains(f"{tag_type}:{tag_filter}")
                tag_expr = cond if tag_expr is None else tag_expr | cond
        filter_expr = filter_expr & tag_expr

    logger.info("Listing snippets", userId=user_id, tagFilter=tag_filter or None)

    try:
        result = table.query(
            KeyConditionExpression=Key("userId").eq(user_id),
            FilterExpression=filter_expr,
        )
        items = result.get("Items", [])
        for item in items:
            item["tags"] = serialize_tags(item.get("tags", []))

        logger.info("Snippets listed", userId=user_id, count=len(items))
        return _res(200, {"snippets": items, "count": len(items)})
    except ClientError as e:
        logger.error("Failed to list snippets", userId=user_id, error=str(e))
        raise
