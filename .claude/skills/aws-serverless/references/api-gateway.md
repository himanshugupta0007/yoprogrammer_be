# API Gateway Reference (HTTP API v2 — Node.js)

## HTTP API vs REST API

| Feature                          | HTTP API v2  | REST API           |
| -------------------------------- | ------------ | ------------------ |
| Cost                             | ~70% cheaper | Higher             |
| Cold start latency               | Lower        | Higher             |
| JWT authorizer                   | Native       | Custom Lambda only |
| Usage plans / API keys           | ❌           | ✅                 |
| Request/response transformations | Limited      | Full               |
| WebSocket                        | ❌           | ❌ (separate)      |

**Default choice: HTTP API v2.** Use REST API only if you need usage plans, API keys, or complex request/response transformations.

---

## Basic HTTP API Setup (SAM)

```yaml
Globals:
  HttpApi:
    CorsConfiguration:
      AllowOrigins: ["https://yourdomain.com"]
      AllowMethods: [GET, POST, PUT, DELETE, OPTIONS]
      AllowHeaders: [Authorization, Content-Type]
    Auth:
      DefaultAuthorizer: JWTAuthorizer
      Authorizers:
        JWTAuthorizer:
          JwtConfiguration:
            issuer: !Sub "https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPoolId}"
            audience: [!Ref UserPoolClientId]
          IdentitySource: "$request.header.Authorization"

MyApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    StageName: !Ref Environment
    AccessLogSettings:
      DestinationArn: !GetAtt ApiLogGroup.Arn

ApiLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    RetentionInDays: 14
```

---

## Lambda Event Shape (HTTP API v2)

```typescript
import { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from "aws-lambda";

export const handler = async (
  event: APIGatewayProxyEventV2,
): Promise<APIGatewayProxyResultV2> => {
  // Path parameters
  const { userId } = event.pathParameters ?? {};

  // Query string
  const { page = "1", limit = "20" } = event.queryStringParameters ?? {};

  // Body (string — parse it)
  const body = event.body ? JSON.parse(event.body) : {};

  // Headers
  const authHeader = event.headers["authorization"];

  // JWT claims (from Cognito authorizer)
  const claims = event.requestContext.authorizer?.jwt?.claims;
  const tenantId = claims?.["custom:tenantId"] as string;

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: result }),
  };
};
```

---

## Standard Error Responses

```typescript
// errors.ts
export class AppError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code: string,
  ) {
    super(message);
    this.name = "AppError";
  }
}

export const errorResponse = (
  statusCode: number,
  code: string,
  message: string,
): APIGatewayProxyResultV2 => ({
  statusCode,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ error: { code, message } }),
});

// Usage
if (!userId) return errorResponse(400, "MISSING_PARAM", "userId is required");
if (!user) return errorResponse(404, "NOT_FOUND", "User not found");
```

---

## Input Validation with Zod

```typescript
import { z } from "zod";

const CreateOrderSchema = z.object({
  productId: z.string().uuid(),
  quantity: z.number().int().positive().max(100),
  shippingAddress: z.object({
    line1: z.string().min(1),
    city: z.string().min(1),
    pincode: z.string().regex(/^\d{6}$/),
  }),
});

export const handler = async (event: APIGatewayProxyEventV2) => {
  const parseResult = CreateOrderSchema.safeParse(
    JSON.parse(event.body ?? "{}"),
  );

  if (!parseResult.success) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        error: {
          code: "VALIDATION_ERROR",
          details: parseResult.error.flatten(),
        },
      }),
    };
  }

  const { productId, quantity, shippingAddress } = parseResult.data;
  // proceed safely
};
```

---

## Lambda Authorizer (Custom Auth)

```typescript
import {
  APIGatewayRequestAuthorizerEventV2,
  APIGatewaySimpleAuthorizerResult,
} from "aws-lambda";
import { verifyToken } from "./auth";

export const handler = async (
  event: APIGatewayRequestAuthorizerEventV2,
): Promise<APIGatewaySimpleAuthorizerResult> => {
  try {
    const token = event.headers?.authorization?.replace("Bearer ", "");
    if (!token) return { isAuthorized: false };

    const claims = await verifyToken(token);
    return {
      isAuthorized: true,
      context: {
        userId: claims.sub,
        tenantId: claims["custom:tenantId"],
        role: claims["custom:role"],
      },
    };
  } catch {
    return { isAuthorized: false };
  }
};
```

```yaml
# SAM authorizer config
Auth:
  DefaultAuthorizer: CustomAuthorizer
  Authorizers:
    CustomAuthorizer:
      FunctionArn: !GetAtt AuthorizerFunction.Arn
      AuthorizerPayloadFormatVersion: "2.0"
      EnableSimpleResponses: true
      Identity:
        Headers: [Authorization]
        ReauthorizeEvery: 300 # cache result for 5 minutes
```

---

## Throttling & Rate Limiting

```yaml
MyApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    DefaultRouteSettings:
      ThrottlingBurstLimit: 100 # max concurrent requests
      ThrottlingRateLimit: 50 # requests per second
    RouteSettings:
      "POST /orders":
        ThrottlingBurstLimit: 20
        ThrottlingRateLimit: 10
```

---

## CORS for Localhost Dev

```yaml
Globals:
  HttpApi:
    CorsConfiguration:
      AllowOrigins:
        - "http://localhost:3000"
        - "https://yourdomain.com"
      AllowMethods: ["*"]
      AllowHeaders: ["*"]
      MaxAge: 600
```
