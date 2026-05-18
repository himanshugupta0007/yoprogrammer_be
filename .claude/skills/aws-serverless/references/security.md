# Security Reference (Lambda / Node.js)

## IAM Least Privilege

Never use `AdministratorAccess` or wildcard `*` on resources. Scope every policy to exact resources.

```yaml
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    Policies:
      # DynamoDB — only the table this function uses
      - DynamoDBCrudPolicy:
          TableName: !Ref MyTable

      # SQS — only send, not receive (if this Lambda only publishes)
      - SQSSendMessagePolicy:
          QueueName: !GetAtt MyQueue.QueueName

      # S3 — read-only on a specific prefix
      - Statement:
          - Effect: Allow
            Action: ["s3:GetObject"]
            Resource: !Sub "arn:aws:s3:::${MyBucket}/uploads/*"

      # Secrets Manager — only the specific secret
      - Statement:
          - Effect: Allow
            Action: ["secretsmanager:GetSecretValue"]
            Resource: !Ref MySecret
```

---

## Secrets Management

Never store secrets (API keys, DB passwords) in environment variables. Use Secrets Manager with in-memory caching.

```typescript
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

const sm = new SecretsManagerClient({});

// Cache in Lambda execution context (warm start reuse)
let cachedSecret: Record<string, string> | null = null;

export const getSecret = async (
  secretName: string,
): Promise<Record<string, string>> => {
  if (cachedSecret) return cachedSecret;

  const response = await sm.send(
    new GetSecretValueCommand({ SecretId: secretName }),
  );
  cachedSecret = JSON.parse(response.SecretString ?? "{}");
  return cachedSecret;
};

// Usage in handler
const { apiKey, dbPassword } = await getSecret(process.env.SECRET_NAME!);
```

---

## Cognito Setup (SAM)

```yaml
UserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    UserPoolName: !Sub "${AWS::StackName}-users"
    AutoVerifiedAttributes: [email]
    Policies:
      PasswordPolicy:
        MinimumLength: 8
        RequireNumbers: true
    Schema:
      - Name: tenantId
        AttributeDataType: String
        Mutable: true

UserPoolClient:
  Type: AWS::Cognito::UserPoolClient
  Properties:
    UserPoolId: !Ref UserPool
    GenerateSecret: false
    ExplicitAuthFlows:
      - ALLOW_USER_PASSWORD_AUTH
      - ALLOW_REFRESH_TOKEN_AUTH
    AccessTokenValidity: 1 # hours
    RefreshTokenValidity: 30 # days
    TokenValidityUnits:
      AccessToken: hours
      RefreshToken: days
```

---

## JWT Verification (custom, without Cognito)

```typescript
import * as jwt from "jsonwebtoken";
import jwksClient from "jwks-rsa";

const client = jwksClient({
  jwksUri: `https://your-auth-domain/.well-known/jwks.json`,
  cache: true,
  cacheMaxAge: 600000, // 10 min
});

export const verifyToken = async (token: string): Promise<jwt.JwtPayload> => {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded || typeof decoded === "string") throw new Error("Invalid token");

  const key = await client.getSigningKey(decoded.header.kid);
  const publicKey = key.getPublicKey();

  return jwt.verify(token, publicKey, {
    algorithms: ["RS256"],
    audience: process.env.JWT_AUDIENCE,
    issuer: process.env.JWT_ISSUER,
  }) as jwt.JwtPayload;
};
```

---

## Input Sanitization

Always sanitize before writing to DynamoDB or returning in responses:

```typescript
import { z } from "zod";
import DOMPurify from "isomorphic-dompurify";

// Sanitize HTML content
const cleanContent = DOMPurify.sanitize(userInput);

// Validate and strip unknown fields with Zod
const safeData = MySchema.parse(rawInput); // throws on invalid
// or
const result = MySchema.safeParse(rawInput); // returns success/error
```

---

## VPC Configuration (if needed)

Only add Lambda to a VPC if it needs to access RDS, ElastiCache, or other VPC resources. VPC adds cold start latency (~100-700ms) unless you use Hyperplane ENIs (enabled by default in newer Lambda).

```yaml
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    VpcConfig:
      SecurityGroupIds: [!Ref LambdaSG]
      SubnetIds: !Split [",", !Ref PrivateSubnetIds]
    Policies:
      - VPCAccessPolicy: {}
```

---

## Security Headers (API Gateway)

Add security headers to all responses via a response interceptor or Lambda middleware:

```typescript
const securityHeaders = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Content-Security-Policy": "default-src 'self'",
};

return {
  statusCode: 200,
  headers: {
    "Content-Type": "application/json",
    ...securityHeaders,
  },
  body: JSON.stringify(result),
};
```
