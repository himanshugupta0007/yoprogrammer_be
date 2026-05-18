# IaC Reference (SAM / CDK)

## SAM Project Structure

```
my-service/
├── template.yaml              # SAM template (all resources)
├── samconfig.toml             # SAM deploy config (environments)
├── src/
│   ├── functions/
│   │   ├── createOrder/
│   │   │   ├── handler.ts
│   │   │   ├── service.ts
│   │   │   └── repository.ts
│   │   └── getOrder/
│   │       └── handler.ts
│   └── shared/
│       ├── types.ts
│       ├── errors.ts
│       └── powertools.ts
├── package.json
└── tsconfig.json
```

---

## SAM Globals (apply to all functions)

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Globals:
  Function:
    Runtime: nodejs24.x
    Architectures: [arm64]
    MemorySize: 256
    Timeout: 30
    Tracing: Active
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        POWERTOOLS_SERVICE_NAME: !Sub "${AWS::StackName}"
        LOG_LEVEL: !If [IsProd, "WARN", "INFO"]
    Layers:
      - !Sub "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsTypeScriptV2:latest"

  HttpApi:
    CorsConfiguration:
      AllowOrigins: ["*"]
      AllowMethods: ["*"]
      AllowHeaders: ["*"]

Conditions:
  IsProd: !Equals [!Ref Environment, prod]
```

---

## samconfig.toml (multi-environment deploy)

```toml
version = 0.1

[default.deploy.parameters]
stack_name = "my-service-dev"
s3_bucket = "my-sam-artifacts"
region = "ap-south-1"
confirm_changeset = false
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Environment=dev"

[prod.deploy.parameters]
stack_name = "my-service-prod"
s3_bucket = "my-sam-artifacts"
region = "ap-south-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Environment=prod"
```

**Deploy commands:**

```bash
sam build
sam deploy                     # uses default (dev)
sam deploy --config-env prod   # uses prod config
```

---

## Full Function Definition

```yaml
CreateOrderFunction:
  Type: AWS::Serverless::Function
  Metadata:
    BuildMethod: esbuild
    BuildProperties:
      Minify: true
      Target: es2020
      EntryPoints: [src/functions/createOrder/handler.ts]
      External: ["@aws-sdk/*"]
  Properties:
    FunctionName: !Sub "${AWS::StackName}-create-order"
    Handler: handler.handler
    Description: Creates a new order
    MemorySize: 512
    Timeout: 30
    ReservedConcurrentExecutions: 100
    Environment:
      Variables:
        TABLE_NAME: !Ref OrdersTable
        QUEUE_URL: !Ref ProcessingQueue
    Policies:
      - DynamoDBCrudPolicy:
          TableName: !Ref OrdersTable
      - SQSSendMessagePolicy:
          QueueName: !GetAtt ProcessingQueue.QueueName
    Events:
      CreateOrder:
        Type: HttpApi
        Properties:
          Path: /orders
          Method: POST
          ApiId: !Ref MyApi
    DeadLetterQueue:
      Type: SQS
      TargetArn: !GetAtt LambdaDLQ.Arn
```

---

## Outputs (for cross-stack references)

```yaml
Outputs:
  ApiUrl:
    Description: API Gateway endpoint
    Value: !Sub "https://${MyApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
    Export:
      Name: !Sub "${AWS::StackName}-ApiUrl"

  TableName:
    Description: DynamoDB table name
    Value: !Ref OrdersTable
    Export:
      Name: !Sub "${AWS::StackName}-TableName"
```

---

## CDK Equivalent (TypeScript)

For projects preferring CDK over SAM:

```typescript
import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as lambdaNodejs from "aws-cdk-lib/aws-lambda-nodejs";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export class MyStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const table = new dynamodb.Table(this, "Table", {
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      pointInTimeRecovery: true,
      timeToLiveAttribute: "ttl",
    });

    const createOrderFn = new lambdaNodejs.NodejsFunction(this, "CreateOrder", {
      entry: "src/functions/createOrder/handler.ts",
      handler: "handler",
      runtime: lambda.Runtime.NODEJS_24_X,
      architecture: lambda.Architecture.ARM_64,
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      tracing: lambda.Tracing.ACTIVE,
      bundling: {
        minify: true,
        externalModules: ["@aws-sdk/*"],
      },
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    table.grantReadWriteData(createOrderFn);

    const api = new apigatewayv2.HttpApi(this, "Api", {
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [apigatewayv2.CorsHttpMethod.ANY],
        allowHeaders: ["*"],
      },
    });

    api.addRoutes({
      path: "/orders",
      methods: [apigatewayv2.HttpMethod.POST],
      integration: new integrations.HttpLambdaIntegration(
        "CreateOrderIntegration",
        createOrderFn,
      ),
    });

    new cdk.CfnOutput(this, "ApiUrl", { value: api.url! });
  }
}
```

---

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "24"
          cache: "npm"

      - run: npm ci

      - uses: aws-actions/setup-sam@v2

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ap-south-1

      - run: sam build
      - run: sam deploy --config-env prod --no-confirm-changeset
```
