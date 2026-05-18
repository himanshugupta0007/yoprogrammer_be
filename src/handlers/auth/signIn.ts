import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import middy from '@middy/core';
import httpJsonBodyParser from '@middy/http-json-body-parser';
import httpErrorHandler from '@middy/http-error-handler';
import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  NotAuthorizedException,
  UserNotConfirmedException,
} from '@aws-sdk/client-cognito-identity-provider';
import { z } from 'zod';
import { logger } from '../../shared/powertools';
import { config } from '../../shared/config';

const cognito = new CognitoIdentityProviderClient({});

const SignInSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const parseResult = SignInSchema.safeParse(event.body);
  if (!parseResult.success) {
    return res(400, { message: parseResult.error.issues[0].message });
  }

  const { email, password } = parseResult.data;
  logger.info('Sign in attempt', { email });

  try {
    const { AuthenticationResult } = await cognito.send(new InitiateAuthCommand({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: config.userPoolClientId,
      AuthParameters: {
        USERNAME: email,
        PASSWORD: password,
      },
    }));

    logger.info('Sign in successful', { email });
    return res(200, {
      idToken: AuthenticationResult!.IdToken,
      accessToken: AuthenticationResult!.AccessToken,
      refreshToken: AuthenticationResult!.RefreshToken,
      expiresIn: AuthenticationResult!.ExpiresIn,
    });
  } catch (err) {
    if (err instanceof NotAuthorizedException) {
      return res(401, { message: 'Incorrect email or password.' });
    }
    if (err instanceof UserNotConfirmedException) {
      return res(403, { message: 'Email not confirmed. Please verify your account first.' });
    }
    logger.error('Sign in failed', { email, error: String(err) });
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
