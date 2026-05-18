# Lambda Patterns Reference (Node.js / TypeScript)

## Handler Structure Best Practices

### Thin Handler Pattern (recommended)

Keep the handler file as a thin entry point. All logic goes in service/repository layers.

```typescript
// handler.ts — only wires things together
import middy from "@middy/core";
import { lambdaHandler } from "./lambdaHandler";
import { httpJsonBodyParser, httpErrorHandler, httpCors } from "./middleware";

export const handler = middy(lambdaHandler)
  .use(httpJsonBodyParser())
  .use(httpCors())
  .use(httpErrorHandler());
```

### Initialize SDK clients OUTSIDE the handler

Clients initialized outside the handler are reused across warm invocations (Lambda execution context reuse).

```typescript
// ✅ CORRECT — initialized once, reused on warm starts
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

const ddbClient = new DynamoDBClient({ region: process.env.AWS_REGION });
const ddb = DynamoDBDocumentClient.from(ddbClient);

export const handler = async (event: ...) => {
  // use ddb here
};

// ❌ WRONG — new client on every invocation
export const handler = async (event: ...) => {
  const ddb = new DynamoDBClient({}); // cold start penalty on every call
};
```

---

## Cold Start Reduction

### 1. Bundle with esbuild (SAM)

```yaml
# template.yaml
Globals:
  Function:
    Runtime: nodejs24.x
    Architectures: [arm64]

MyFunction:
  Type: AWS::Serverless::Function
  Metadata:
    BuildMethod: esbuild
    BuildProperties:
      Minify: true
      Target: es2020
      Sourcemap: false
      EntryPoints:
        - src/handler.ts
      External:
        - "@aws-sdk/*" # already available in Lambda runtime
```

### 2. Use ARM64 (Graviton2)

- ~20% faster cold starts, ~20% cheaper per GB-second
- Just add `Architectures: [arm64]` — no code changes needed for Node.js

### 3. Increase Memory to 512MB–1024MB for latency-sensitive functions

- Lambda CPU scales proportionally with memory
- Use AWS Lambda Power Tuning tool to find the optimal memory/cost trade-off

### 4. Keep init code minimal

```typescript
// ✅ Lazy-load heavy modules only when needed
let heavyLib: typeof import("some-heavy-lib") | undefined;

export const handler = async () => {
  if (!heavyLib) {
    heavyLib = await import("some-heavy-lib");
  }
  // use heavyLib
};
```

---

## Lambda Layers

Use layers for:

- Shared utilities (custom logger wrapper, error types)
- Large dependencies shared across many functions (e.g., Powertools)

```yaml
# template.yaml
PowertoolsLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: powertools-layer
    ContentUri: layers/powertools/
    CompatibleRuntimes: [nodejs24.x]
    CompatibleArchitectures: [arm64]

MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    Layers:
      - !Ref PowertoolsLayer
```

---

## SQS Event Processing Pattern

```typescript
import { SQSEvent, SQSRecord, SQSBatchResponse } from "aws-lambda";
import { Logger } from "@aws-lambda-powertools/logger";

const logger = new Logger();

export const handler = async (event: SQSEvent): Promise<SQSBatchResponse> => {
  const batchItemFailures: { itemIdentifier: string }[] = [];

  await Promise.all(
    event.Records.map(async (record: SQSRecord) => {
      try {
        const body = JSON.parse(record.body);
        await processMessage(body);
      } catch (err) {
        logger.error("Failed to process record", {
          messageId: record.messageId,
          err,
        });
        // Report partial failure — only failed messages re-queued
        batchItemFailures.push({ itemIdentifier: record.messageId });
      }
    }),
  );

  return { batchItemFailures };
};
```

**SAM config for SQS trigger:**

```yaml
Events:
  SQSEvent:
    Type: SQS
    Properties:
      Queue: !GetAtt MyQueue.Arn
      BatchSize: 10
      FunctionResponseTypes:
        - ReportBatchItemFailures # critical — enables partial batch failure
      MaximumBatchingWindowInSeconds: 5
```

---

## S3 Event Trigger Pattern

```typescript
import { S3Event, S3EventRecord } from "aws-lambda";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";

const s3 = new S3Client({});

export const handler = async (event: S3Event): Promise<void> => {
  await Promise.all(
    event.Records.map(async (record: S3EventRecord) => {
      const bucket = record.s3.bucket.name;
      const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, " "));

      const response = await s3.send(
        new GetObjectCommand({ Bucket: bucket, Key: key }),
      );
      const content = await response.Body?.transformToString();
      // process content
    }),
  );
};
```

---

## Idempotency Pattern (for retryable operations)

```typescript
import { makeHandlerIdempotent } from "@aws-lambda-powertools/idempotency";
import { DynamoDBPersistenceLayer } from "@aws-lambda-powertools/idempotency/dynamodb";

const persistenceStore = new DynamoDBPersistenceLayer({
  tableName: process.env.IDEMPOTENCY_TABLE!,
});

export const handler = makeHandlerIdempotent(
  async (event: APIGatewayProxyEventV2) => {
    // This block runs ONCE per unique event, even if Lambda retries
    return await processOrder(event.body);
  },
  { persistenceStore },
);
```

```yaml
IdempotencyTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub "${AWS::StackName}-idempotency"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: id
        AttributeType: S
    KeySchema:
      - AttributeName: id
        KeyType: HASH
    TimeToLiveSpecification:
      AttributeName: expiration
      Enabled: true
```

---

## Environment Variable Validation

Always validate required env vars at cold start (not inside handler):

```typescript
// config.ts — validated once at cold start
const getEnv = (key: string): string => {
  const value = process.env[key];
  if (!value) throw new Error(`Missing required environment variable: ${key}`);
  return value;
};

export const config = {
  tableName: getEnv("TABLE_NAME"),
  region: getEnv("AWS_REGION"),
  serviceName: getEnv("SERVICE_NAME"),
};
```

---

## Scheduled / EventBridge Cron Pattern

```typescript
import { EventBridgeEvent } from "aws-lambda";

export const handler = async (
  event: EventBridgeEvent<string, unknown>,
): Promise<void> => {
  console.log("Scheduled job triggered", { time: event.time });
  await runDailyJob();
};
```

```yaml
Events:
  DailySchedule:
    Type: Schedule
    Properties:
      Schedule: cron(0 2 * * ? *) # 2 AM UTC daily
      Enabled: true
```
