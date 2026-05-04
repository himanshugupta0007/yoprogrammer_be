# yoprogrammer_be

Backend system for YoProgrammer, built with TypeScript and deployed on AWS using SAM (Serverless Application Model).

## Tech Stack

- **Runtime:** Node.js 24.x (AWS Lambda)
- **Language:** TypeScript (ES2020)
- **Infrastructure:** AWS SAM (CloudFormation)
- **Auth:** Amazon Cognito
- **AI/ML:** Amazon Bedrock (`amazon.titan-embed-text-v2:0`)
- **Messaging:** Amazon SQS

## Prerequisites

- [Node.js](https://nodejs.org/) v18+
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- AWS account with appropriate permissions

## Getting Started

1. **Clone the repo**
   ```bash
   git clone https://github.com/himanshugupta0007/yoprogrammer_be.git
   cd yoprogrammer_be
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Fill in the required values in `.env`:
   | Variable | Description |
   |---|---|
   | `STAGE` | Deployment stage (`dev` / `prod`) |
   | `COGNITO_USER_POOL_ID` | Cognito User Pool ID |
   | `COGNITO_USER_POOL_CLIENT_ID` | Cognito App Client ID |
   | `BEDROCK_MODEL_ID` | Bedrock model ID (default: `amazon.titan-embed-text-v2:0`) |
   | `SQS_QUEUE_URL` | SQS queue URL |

## Deployment

Deploy using AWS SAM:

```bash
sam build
sam deploy --guided
```

SAM parameters:
- `Stage` — `dev` (default) or `prod`
- `BedrockModelId` — Bedrock model ID
- `SQSQueueUrl` — SQS queue URL

## AWS Resources Provisioned

- **Cognito User Pool** — Email-based authentication with SRP auth flow
- **Cognito User Pool Client** — App client with 1-hour access/ID tokens and 30-day refresh tokens

## Repository

- GitHub: https://github.com/himanshugupta0007/yoprogrammer_be
- Issues: https://github.com/himanshugupta0007/yoprogrammer_be/issues

## License

ISC
