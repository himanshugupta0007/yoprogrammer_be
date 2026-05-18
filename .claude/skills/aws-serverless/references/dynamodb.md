# Cost Optimization Reference

## Lambda Cost Formula

```
Cost = (invocations × $0.0000002) + (GB-seconds × $0.0000166667)
GB-seconds = (memory_MB / 1024) × duration_seconds × invocations
```

AWS always provides 1M free invocations and 400,000 GB-seconds/month.

---

## Memory Tuning

More memory = more CPU = faster execution = potentially lower cost (shorter duration).

**Rule of thumb:**

- CPU-bound (data processing, JSON parsing): increase memory → faster → cheaper
- I/O-bound (DynamoDB calls, HTTP): more memory rarely helps much

**Use AWS Lambda Power Tuning tool** to find optimal memory:

```bash
# Deploy via SAR: https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:451282421402:applications~aws-lambda-power-tuning
# Then invoke with:
{
  "lambdaARN": "arn:aws:lambda:...",
  "powerValues": [128, 256, 512, 1024, 1769, 3008],
  "num": 50,
  "payload": {},
  "parallelInvocation": true,
  "strategy": "cost"  # or "speed" or "balanced"
}
```

---

## ARM64 (Graviton2)

- ~20% cheaper per GB-second than x86
- ~20% faster cold starts
- Zero code changes for Node.js
- Just add `Architectures: [arm64]` in SAM

```yaml
Globals:
  Function:
    Architectures: [arm64]
```

---

## Reserved vs On-Demand Concurrency

| Mode                    | When to Use                                 | Cost Impact                        |
| ----------------------- | ------------------------------------------- | ---------------------------------- |
| On-demand               | Default, variable traffic                   | Pay per use                        |
| Reserved concurrency    | Prevent throttling/noisy neighbor           | Same cost, caps max concurrency    |
| Provisioned concurrency | Eliminate cold starts for latency-sensitive | ~3× more expensive — use sparingly |

Only use Provisioned Concurrency for customer-facing APIs with strict p99 SLAs. For background jobs, cold starts don't matter.

---

## DynamoDB Cost

- **On-demand**: pay per read/write request unit — best for variable traffic
- **Provisioned**: set RCU/WCU — best for steady, predictable traffic with auto-scaling

**Read/write cost:**

- 1 RCU = 1 strongly consistent read of up to 4KB
- 1 WCU = 1 write of up to 1KB

**Optimization tips:**

- Use `ProjectionExpression` to fetch only needed attributes (reduces RCU)
- Use `BatchGetItem` instead of N individual `GetItem` calls
- Design access patterns to avoid Scan (Scan reads entire table)
- Enable TTL for temporary data (deletion is free)

---

## SQS Cost

- Standard queue: ~$0.40 per million requests
- First 1M requests/month free

SQS is extremely cheap — optimize Lambda batch size instead:

- Higher batch size (10–100) = fewer Lambda invocations = lower Lambda cost
- Trade-off: larger batch = longer processing time per invocation

---

## API Gateway Cost

- HTTP API: $1.00 per million requests
- REST API: $3.50 per million requests

Switch to HTTP API unless you need REST API-specific features. Same Lambda code works with both.

---

## S3 Cost Reduction

```typescript
// Use S3 Transfer Acceleration only when needed (extra cost)
// Use presigned URLs to let clients upload directly — avoids Lambda processing large files

import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const s3 = new S3Client({});

const presignedUrl = await getSignedUrl(
  s3,
  new PutObjectCommand({
    Bucket: process.env.BUCKET!,
    Key: `uploads/${fileId}`,
  }),
  { expiresIn: 300 }, // 5 minutes
);

return { uploadUrl: presignedUrl, fileId };
// Client uploads directly to S3 — Lambda doesn't touch the file bytes
```

---

## CloudWatch Logs Cost

Logs cost $0.50/GB ingested. For high-volume functions, reduce log verbosity in production.

```typescript
// Use LOG_LEVEL env var to control verbosity
const logger = new Logger({
  logLevel: (process.env.LOG_LEVEL as LogLevel) ?? "INFO",
});

// In SAM: set LOG_LEVEL=WARN for production to reduce log volume
```

Set log retention to avoid unbounded storage costs:

```yaml
MyFunctionLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub "/aws/lambda/${MyFunction}"
    RetentionInDays: 14 # don't keep forever
```

---

## Cost Monitoring

```yaml
MonthlyCostBudget:
  Type: AWS::Budgets::Budget
  Properties:
    Budget:
      BudgetName: !Sub "${AWS::StackName}-monthly"
      BudgetLimit:
        Amount: 50
        Unit: USD
      TimeUnit: MONTHLY
      BudgetType: COST
    NotificationsWithSubscribers:
      - Notification:
          NotificationType: ACTUAL
          ComparisonOperator: GREATER_THAN
          Threshold: 80 # alert at 80% of budget
        Subscribers:
          - SubscriptionType: EMAIL
            Address: your@email.com
```
