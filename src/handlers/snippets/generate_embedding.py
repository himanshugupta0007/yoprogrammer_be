import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from src.shared.powertools import logger, tracer

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EMBEDDINGS_TABLE_NAME"])

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")


@tracer.capture_lambda_handler(capture_response=False)
def handler(event, context):
    failures = []

    for record in event["Records"]:
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            snippet_id = body["snippetId"]
            code = body["code"]
            user_id = body.get("userId")

            logger.info("Generating embedding", snippetId=snippet_id, modelId=MODEL_ID)

            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "inputText": code,
                    "dimensions": 1024,
                    "normalize": True,
                }),
            )

            result = json.loads(response["body"].read())
            embedding = result["embedding"]
            token_count = result["inputTextTokenCount"]

            table.put_item(Item={
                "snippetId": snippet_id,
                "userId": user_id,
                "embedding": embedding,
                "tokenCount": token_count,
                "modelId": MODEL_ID,
                "embeddedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

            logger.info(
                "Embedding stored",
                snippetId=snippet_id,
                dimensions=len(embedding),
                tokenCount=token_count,
            )

        except (KeyError, json.JSONDecodeError) as e:
            logger.error("Malformed message, skipping", messageId=message_id, error=str(e))
            # do NOT add to failures — malformed messages should go to DLQ after maxReceiveCount

        except ClientError as e:
            logger.error("AWS error, retrying", messageId=message_id, error=str(e))
            failures.append({"itemIdentifier": message_id})

        except Exception as e:
            logger.error("Unexpected error", messageId=message_id, error=str(e))
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
