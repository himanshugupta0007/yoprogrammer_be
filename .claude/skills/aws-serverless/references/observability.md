# Observability Reference (CloudWatch / X-Ray / Powertools)

## AWS Lambda Powertools Setup (TypeScript)

```typescript
// powertools.ts — shared singleton, import into every Lambda
import { Logger } from "@aws-lambda-powertools/logger";
import { Tracer } from "@aws-lambda-powertools/tracer";
import { Metrics, MetricUnit } from "@aws-lambda-powertools/metrics";

export const logger = new Logger({
  serviceName: process.env.SERVICE_NAME!,
  logLevel:
    (process.env.LOG_LEVEL as "DEBUG" | "INFO" | "WARN" | "ERROR") ?? "INFO",
});

export const tracer = new Tracer({ serviceName: process.env.SERVICE_NAME! });

export const metrics = new Metrics({
  namespace: process.env.METRICS_NAMESPACE ?? "MyApp",
  serviceName: process.env.SERVICE_NAME!,
});
```

---

## Structured Logging

```typescript
import { logger } from "./powertools";

// ✅ Always log with context object, not string concatenation
logger.info("Order processed", {
  orderId,
  userId,
  amount,
  durationMs: Date.now() - startTime,
});

logger.error("DynamoDB write failed", {
  error: err instanceof Error ? err.message : String(err),
  tableName: process.env.TABLE_NAME,
  operation: "PutCommand",
});

// Add persistent keys (available in all subsequent log statements)
logger.appendKeys({ tenantId, requestId: event.requestContext.requestId });
```

---

## Custom Metrics

```typescript
import { metrics, MetricUnit } from "./powertools";

// Record a custom metric
metrics.addMetric("OrdersPlaced", MetricUnit.Count, 1);
metrics.addMetric("PaymentAmount", MetricUnit.None, amount);
metrics.addMetric("ProcessingDuration", MetricUnit.Milliseconds, durationMs);

// Add dimensions
metrics.addDimension("Environment", process.env.ENVIRONMENT ?? "prod");

// Flush at end of handler (or use @metrics.logMetrics decorator)
metrics.publishStoredMetrics();
```

---

## X-Ray Tracing

```typescript
import { tracer } from './powertools';

export const handler = async (event: ...) => {
  // Create a custom subsegment
  const segment = tracer.getSegment();
  const subsegment = segment?.addNewSubsegment('DynamoDB::GetUser');

  try {
    const user = await getUser(userId);
    subsegment?.addAnnotation('userId', userId);
    subsegment?.addMetadata('result', user);
    return user;
  } catch (err) {
    subsegment?.addError(err as Error);
    throw err;
  } finally {
    subsegment?.close();
  }
};
```

---

## SAM Observability Configuration

```yaml
Globals:
  Function:
    Tracing: Active # X-Ray on all functions
    Environment:
      Variables:
        POWERTOOLS_SERVICE_NAME: !Sub "${AWS::StackName}"
        LOG_LEVEL: INFO
        POWERTOOLS_METRICS_NAMESPACE: MyApp
    Layers:
      - !Sub "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsTypeScriptV2:latest"

  Api:
    TracingEnabled: true # X-Ray on API Gateway
    AccessLogDestination:
      DestinationArn: !GetAtt ApiLogGroup.Arn
    AccessLogFormat: '{"requestId":"$context.requestId","ip":"$context.identity.sourceIp","requestTime":"$context.requestTime","httpMethod":"$context.httpMethod","routeKey":"$context.routeKey","status":"$context.status","responseLength":"$context.responseLength","integrationLatency":"$context.integrationLatency"}'
```

---

## CloudWatch Log Insights Queries

**Find all errors in last 1 hour:**

```
fields @timestamp, @message, service, error
| filter level = "ERROR"
| sort @timestamp desc
| limit 50
```

**Find cold starts:**

```
filter @message like /INIT_START/
| stats count(*) as coldStarts by bin(5m)
```

**P99 duration:**

```
filter @type = "REPORT"
| stats pct(@duration, 99) as p99, avg(@duration) as avg by bin(5m)
```

**Trace a specific request:**

```
fields @timestamp, @message
| filter @requestId = "abc-123-xyz"
| sort @timestamp asc
```

**Find throttles:**

```
filter @message like /Task timed out/
| stats count(*) as timeouts by bin(5m)
```

---

## CloudWatch Alarms (SAM)

```yaml
ErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub "${AWS::StackName}-error-rate"
    MetricName: Errors
    Namespace: AWS/Lambda
    Dimensions:
      - Name: FunctionName
        Value: !Ref MyFunction
    Statistic: Sum
    Period: 60
    EvaluationPeriods: 2
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    TreatMissingData: notBreaching
    AlarmActions:
      - !Ref AlertTopic

HighDurationAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub "${AWS::StackName}-high-duration"
    MetricName: Duration
    Namespace: AWS/Lambda
    Dimensions:
      - Name: FunctionName
        Value: !Ref MyFunction
    ExtendedStatistic: p99
    Period: 300
    EvaluationPeriods: 1
    Threshold: 5000 # alert if p99 > 5 seconds
    ComparisonOperator: GreaterThanThreshold
```

---

## Dashboard (SAM)

```yaml
AppDashboard:
  Type: AWS::CloudWatch::Dashboard
  Properties:
    DashboardName: !Sub "${AWS::StackName}-dashboard"
    DashboardBody: !Sub |
      {
        "widgets": [
          {
            "type": "metric",
            "properties": {
              "title": "Lambda Invocations & Errors",
              "metrics": [
                ["AWS/Lambda", "Invocations", "FunctionName", "${MyFunction}"],
                ["AWS/Lambda", "Errors", "FunctionName", "${MyFunction}"]
              ],
              "period": 60,
              "stat": "Sum",
              "view": "timeSeries"
            }
          }
        ]
      }
```
