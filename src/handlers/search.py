import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer
from src.shared.tags import serialize_tags

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
embeddings_table = dynamodb.Table(os.environ["EMBEDDINGS_TABLE_NAME"])
snippets_table = dynamodb.Table(os.environ["SNIPPETS_TABLE_NAME"])

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")
DEFAULT_TOP_K = 5
MAX_TOP_K = 20


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _res(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
        "body": json.dumps(body, cls=_DecimalEncoder),
    }


def _embed(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True,
        }),
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def _dot(a: list[float], b) -> float:
    # Vectors are L2-normalized (normalize=True) so cosine similarity == dot product
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _scan_user_embeddings(user_id: str) -> list[dict]:
    items = []
    kwargs = {"FilterExpression": Attr("userId").eq(user_id)}
    while True:
        resp = embeddings_table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def _batch_get_snippets(user_id: str, snippet_ids: list[str]) -> dict[str, dict]:
    if not snippet_ids:
        return {}
    table_name = snippets_table.name
    result = {}
    for i in range(0, len(snippet_ids), 100):
        chunk = snippet_ids[i:i + 100]
        keys = [{"userId": user_id, "snippetId": sid} for sid in chunk]
        resp = dynamodb.batch_get_item(
            RequestItems={table_name: {"Keys": keys}}
        )
        for item in resp.get("Responses", {}).get(table_name, []):
            result[item["snippetId"]] = item
    return result


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

    query = str(body.get("query", "")).strip()
    if not query:
        return _res(400, {"message": "query is required"})
    if len(query) > 2000:
        return _res(400, {"message": "query must be 2000 characters or fewer"})

    top_k = min(int(body.get("topK", DEFAULT_TOP_K)), MAX_TOP_K)

    logger.info("Semantic search", userId=user_id, queryLength=len(query), topK=top_k)

    try:
        query_vector = _embed(query)
    except ClientError as e:
        logger.error("Bedrock embed failed", error=str(e))
        return _res(502, {"message": "Failed to embed query"})

    try:
        embeddings = _scan_user_embeddings(user_id)
    except ClientError as e:
        logger.error("Embeddings scan failed", error=str(e))
        raise

    if not embeddings:
        return _res(200, {"results": [], "count": 0})

    scored = [
        {"snippetId": e["snippetId"], "score": _dot(query_vector, e["embedding"])}
        for e in embeddings
        if e.get("embedding")
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_k]

    try:
        snippet_map = _batch_get_snippets(user_id, [s["snippetId"] for s in top])
    except ClientError as e:
        logger.error("Snippet batch fetch failed", error=str(e))
        raise

    results = []
    for entry in top:
        snippet = snippet_map.get(entry["snippetId"])
        if not snippet or snippet.get("isDeleted"):
            continue
        results.append({
            "snippetId": snippet["snippetId"],
            "title": snippet["title"],
            "language": snippet["language"],
            "code": snippet["code"],
            "notes": snippet.get("notes", ""),
            "tags": serialize_tags(snippet.get("tags", [])),
            "createdAt": snippet["createdAt"],
            "score": round(float(entry["score"]), 4),
        })

    logger.info("Search complete", userId=user_id, totalEmbeddings=len(embeddings), matched=len(results))
    return _res(200, {"results": results, "count": len(results)})
