import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer
from src.shared.tags import parse_input_tags, serialize_tags

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["SNIPPETS_TABLE_NAME"])

sqs = boto3.client("sqs")
EMBEDDING_QUEUE_URL = os.environ["EMBEDDING_QUEUE_URL"]


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

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _res(400, {"message": "Invalid JSON body"})

    title = str(body.get("title", "")).strip()
    code = str(body.get("code", "")).strip()
    language = str(body.get("language", "")).strip()
    notes = str(body.get("notes", "")).strip()
    tags_raw = body.get("tags", [])

    if not title:
        return _res(400, {"message": "title is required"})
    if not code:
        return _res(400, {"message": "code is required"})
    if not language:
        return _res(400, {"message": "language is required"})

    if not isinstance(tags_raw, list):
        return _res(400, {"message": "tags must be an array"})
    if len(tags_raw) > 10:
        return _res(400, {"message": "tags must have at most 10 items"})

    try:
        tags = parse_input_tags(tags_raw)
    except ValueError as e:
        return _res(400, {"message": str(e)})

    snippet_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    item = {
        "userId": user_id,
        "snippetId": snippet_id,
        "title": title,
        "code": code,
        "language": language,
        "createdAt": created_at,
    }
    if tags:
        item["tags"] = tags
    if notes:
        item["notes"] = notes

    logger.info("Creating snippet", userId=user_id, language=language, tagCount=len(tags))

    try:
        table.put_item(Item=item)
    except ClientError as e:
        logger.error("Failed to create snippet", userId=user_id, error=str(e))
        raise

    try:
        sqs.send_message(
            QueueUrl=EMBEDDING_QUEUE_URL,
            MessageBody=json.dumps({"snippetId": snippet_id, "userId": user_id, "code": code}),
        )
        logger.info("Snippet created", userId=user_id, snippetId=snippet_id)
    except ClientError as e:
        logger.error("Failed to queue embedding", userId=user_id, snippetId=snippet_id, error=str(e))
        raise

    return _res(201, {**item, "tags": serialize_tags(tags)})
