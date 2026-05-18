# Async Patterns Reference (SQS / SNS / EventBridge)

## When to Use Which

| Service            | Best For                                                                   |
| ------------------ | -------------------------------------------------------------------------- |
| **SQS Standard**   | Decoupled async processing, retries, DLQ, at-least-once delivery           |
| **SQS FIFO**       | Ordered processing, exactly-once delivery (lower throughput: 300 msg/s)    |
| **SNS**            | Fan-out to multiple consumers, pub/sub                                     |
| **EventBridge**    | Event routing by rules, cross-account, SaaS integrations, scheduled events |
| **Step Functions** | Multi-step workflows, saga pattern, long-running processes with state      |

---

## SQS — Standard Queue with DLQ

```yaml
# template.yaml
MyQueue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub "${AWS::StackName}-queue"
    VisibilityTimeout: 180 # must be >= 6x Lambda timeout
    MessageRetentionPeriod: 86400 # 1 day
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt MyDLQ.Arn
      maxReceiveCount: 3 # retry 3x before sending to DLQ

MyDLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub "${AWS::StackName}-dlq"
    MessageRetentionPeriod: 1209600 # 14 days — time to investigate failures

DLQAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub "${AWS::StackName}-dlq-messages"
    MetricName: ApproximateNumberOfMessagesVisible
    Namespace: AWS/SQS
    Dimensions:
      - Name: QueueName
        Value: !GetAtt MyDLQ.QueueName
    Statistic: Sum
    Period: 60
    EvaluationPeriods: 1
    Threshold: 1
    ComparisonOperator: GreaterThanOrEqualToThreshold
    AlarmActions:
      - !Ref AlertTopic # SNS topic → email/PagerDuty
```

**VisibilityTimeout rule:** must be at least 6× Lambda timeout to prevent duplicate processing during retries.

---

## SNS → SQS Fan-Out Pattern

```yaml
MyTopic:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub "${AWS::StackName}-topic"

EmailQueue:
  Type: AWS::SQS::Queue
  Properties:
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt EmailDLQ.Arn
      maxReceiveCount: 3

AnalyticsQueue:
  Type: AWS::SQS::Queue

EmailSubscription:
  Type: AWS::SNS::Subscription
  Properties:
    TopicArn: !Ref MyTopic
    Protocol: sqs
    Endpoint: !GetAtt EmailQueue.Arn
    FilterPolicy: # optional: only route certain events
      eventType:
        - ORDER_PLACED

AnalyticsSubscription:
  Type: AWS::SNS::Subscription
  Properties:
    TopicArn: !Ref MyTopic
    Protocol: sqs
    Endpoint: !GetAtt AnalyticsQueue.Arn

# Allow SNS to send to SQS
EmailQueuePolicy:
  Type: AWS::SQS::QueuePolicy
  Properties:
    Queues: [!Ref EmailQueue]
    PolicyDocument:
      Statement:
        - Effect: Allow
          Principal: { Service: sns.amazonaws.com }
          Action: sqs:SendMessage
          Resource: !GetAtt EmailQueue.Arn
          Condition:
            ArnEquals:
              aws:SourceArn: !Ref MyTopic
```

**Publishing to SNS from Node.js:**

```typescript
import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";

const sns = new SNSClient({});

await sns.send(
  new PublishCommand({
    TopicArn: process.env.TOPIC_ARN!,
    Message: JSON.stringify({ orderId, userId, amount }),
    MessageAttributes: {
      eventType: { DataType: "String", StringValue: "ORDER_PLACED" },
    },
  }),
);
```

---

## Sending to SQS from Node.js

```typescript
import { SQSClient, SendMessageCommand } from "@aws-sdk/client-sqs";

const sqs = new SQSClient({});

await sqs.send(
  new SendMessageCommand({
    QueueUrl: process.env.QUEUE_URL!,
    MessageBody: JSON.stringify({ jobId, payload }),
    MessageGroupId: tenantId, // for FIFO queues only
    MessageDeduplicationId: jobId, // for FIFO queues only
    DelaySeconds: 0,
  }),
);
```

---

## EventBridge — Custom Event Bus

```yaml
MyEventBus:
  Type: AWS::Events::EventBus
  Properties:
    Name: !Sub "${AWS::StackName}-bus"

OrderPlacedRule:
  Type: AWS::Events::Rule
  Properties:
    EventBusName: !Ref MyEventBus
    EventPattern:
      source: ["myapp.orders"]
      detail-type: ["OrderPlaced"]
    Targets:
      - Id: ProcessOrderTarget
        Arn: !GetAtt ProcessOrderFunction.Arn

ProcessOrderPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref ProcessOrderFunction
    Action: lambda:InvokeFunction
    Principal: events.amazonaws.com
    SourceArn: !GetAtt OrderPlacedRule.Arn
```

**Publishing to EventBridge from Node.js:**

```typescript
import {
  EventBridgeClient,
  PutEventsCommand,
} from "@aws-sdk/client-eventbridge";

const eb = new EventBridgeClient({});

await eb.send(
  new PutEventsCommand({
    Entries: [
      {
        EventBusName: process.env.EVENT_BUS_NAME!,
        Source: "myapp.orders",
        DetailType: "OrderPlaced",
        Detail: JSON.stringify({
          orderId,
          userId,
          amount,
          timestamp: new Date().toISOString(),
        }),
      },
    ],
  }),
);
```

---

## Step Functions (Express Workflow — for APIs)

Use Express Workflows (not Standard) when:

- Workflow completes in < 5 minutes
- You need synchronous execution (API waits for result)
- High volume (Standard Workflows charge per state transition)

```yaml
OrderWorkflow:
  Type: AWS::Serverless::StateMachine
  Properties:
    Type: EXPRESS
    Definition:
      StartAt: ValidateOrder
      States:
        ValidateOrder:
          Type: Task
          Resource: !GetAtt ValidateLambda.Arn
          Next: ChargePayment
          Catch:
            - ErrorEquals: [ValidationError]
              Next: FailState
        ChargePayment:
          Type: Task
          Resource: !GetAtt ChargeLambda.Arn
          Next: UpdateInventory
          Retry:
            - ErrorEquals: [States.TaskFailed]
              MaxAttempts: 2
              IntervalSeconds: 2
        UpdateInventory:
          Type: Task
          Resource: !GetAtt InventoryLambda.Arn
          Next: NotifyUser
        NotifyUser:
          Type: Task
          Resource: !GetAtt NotifyLambda.Arn
          End: true
        FailState:
          Type: Fail
          Error: OrderFailed
    Policies:
      - LambdaInvokePolicy:
          FunctionName: !Ref ValidateLambda
      - LambdaInvokePolicy:
          FunctionName: !Ref ChargeLambda
```

---

## Async API Pattern (long-running jobs)

When a job takes > 29 seconds (API Gateway hard limit), use async pattern:

```
POST /jobs           → Lambda creates job record in DynamoDB, sends to SQS, returns jobId
GET  /jobs/{jobId}   → Lambda reads job status from DynamoDB (polling)
```

```typescript
// POST /jobs handler
export const handler = async (event: APIGatewayProxyEventV2) => {
  const jobId = crypto.randomUUID();

  // Save initial status
  await ddb.send(
    new PutCommand({
      TableName: process.env.TABLE_NAME!,
      Item: {
        PK: `JOB#${jobId}`,
        SK: "STATUS",
        status: "PENDING",
        createdAt: new Date().toISOString(),
      },
    }),
  );

  // Queue the work
  await sqs.send(
    new SendMessageCommand({
      QueueUrl: process.env.QUEUE_URL!,
      MessageBody: JSON.stringify({ jobId, ...JSON.parse(event.body ?? "{}") }),
    }),
  );

  return {
    statusCode: 202,
    body: JSON.stringify({ jobId, statusUrl: `/jobs/${jobId}` }),
  };
};
```
