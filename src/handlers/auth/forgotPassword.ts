import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import middy from '@middy/core';
import httpJsonBodyParser from '@middy/http-json-body-parser';
import httpErrorHandler from '@middy/http-error-handler';
import {
  CognitoIdentityProviderClient,
  ForgotPasswordCommand,
  UserNotFoundException,
} from '@aws-sdk/client-cognito-identity-provider';
import { z } from 'zod';
import { logger } from '../../shared/powertools';
import { config } from '../../shared/config';

const cognito = new CognitoIdentityProviderClient({});

const ForgotPasswordSchema = z.object({
  email: z.string().email(),
});

const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const parseResult = ForgotPasswordSchema.safeParse(event.body);
  if (!parseResult.success) {
    return res(400, { message: parseResult.error.issues[0].message });
  }

  const { email } = parseResult.data;
  logger.info('Forgot password request', { email });

  try {
    await cognito.send(new ForgotPasswordCommand({
      ClientId: config.userPoolClientId,
      Username: email,
    }));

    return res(200, { message: 'Password reset code sent to your email.' });
  } catch (err) {
    if (err instanceof UserNotFoundException) {
      // Return 200 to avoid leaking which emails are registered
      return res(200, { message: 'Password reset code sent to your email.' });
    }
    logger.error('Forgot password failed', { email, error: String(err) });
    throw err;
  }
};

export const handler = middy(lambdaHandler)
  .use(httpJsonBodyParser())
  .use(httpErrorHandler());

function res(statusCode: number, body: object): APIGatewayProxyResult {
  return {
    statusCode,
    headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}
