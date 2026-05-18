import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import middy from '@middy/core';
import httpJsonBodyParser from '@middy/http-json-body-parser';
import httpErrorHandler from '@middy/http-error-handler';
import {
  CognitoIdentityProviderClient,
  SignUpCommand,
  UsernameExistsException,
  InvalidPasswordException,
} from '@aws-sdk/client-cognito-identity-provider';
import { z } from 'zod';
import { logger } from '../../shared/powertools';
import { config } from '../../shared/config';

const cognito = new CognitoIdentityProviderClient({});

const SignUpSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().optional(),
});

const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const parseResult = SignUpSchema.safeParse(event.body);
  if (!parseResult.success) {
    return res(400, { message: parseResult.error.issues[0].message });
  }

  const { email, password, name } = parseResult.data;
  logger.info('Sign up attempt', { email });

  try {
    await cognito.send(new SignUpCommand({
      ClientId: config.userPoolClientId,
      Username: email,
      Password: password,
      UserAttributes: [
        { Name: 'email', Value: email },
        ...(name ? [{ Name: 'name', Value: name }] : []),
      ],
    }));

    logger.info('Sign up successful', { email });
    return res(200, { message: 'Sign up successful. Check your email for a verification code.' });
  } catch (err) {
    if (err instanceof UsernameExistsException) {
      return res(409, { message: 'An account with this email already exists.' });
    }
    if (err instanceof InvalidPasswordException) {
      return res(400, { message: (err as Error).message });
    }
    logger.error('Sign up failed', { email, error: String(err) });
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
