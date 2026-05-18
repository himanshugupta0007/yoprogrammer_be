import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import middy from '@middy/core';
import httpJsonBodyParser from '@middy/http-json-body-parser';
import httpErrorHandler from '@middy/http-error-handler';
import {
  CognitoIdentityProviderClient,
  ConfirmSignUpCommand,
  CodeMismatchException,
  ExpiredCodeException,
} from '@aws-sdk/client-cognito-identity-provider';
import { z } from 'zod';
import { logger } from '../../shared/powertools';
import { config } from '../../shared/config';

const cognito = new CognitoIdentityProviderClient({});

const ConfirmSignUpSchema = z.object({
  email: z.string().email(),
  code: z.string().min(1),
});

const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const parseResult = ConfirmSignUpSchema.safeParse(event.body);
  if (!parseResult.success) {
    return res(400, { message: parseResult.error.issues[0].message });
  }

  const { email, code } = parseResult.data;
  logger.info('Confirm sign up attempt', { email });

  try {
    await cognito.send(new ConfirmSignUpCommand({
      ClientId: config.userPoolClientId,
      Username: email,
      ConfirmationCode: code,
    }));

    logger.info('Email confirmed', { email });
    return res(200, { message: 'Email confirmed. You can now sign in.' });
  } catch (err) {
    if (err instanceof CodeMismatchException) {
      return res(400, { message: 'Invalid verification code.' });
    }
    if (err instanceof ExpiredCodeException) {
      return res(400, { message: 'Verification code has expired. Please request a new one.' });
    }
    logger.error('Confirm sign up failed', { email, error: String(err) });
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
