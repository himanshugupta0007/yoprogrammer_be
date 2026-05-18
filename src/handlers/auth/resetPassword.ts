import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import middy from '@middy/core';
import httpJsonBodyParser from '@middy/http-json-body-parser';
import httpErrorHandler from '@middy/http-error-handler';
import {
  CognitoIdentityProviderClient,
  ConfirmForgotPasswordCommand,
  CodeMismatchException,
  ExpiredCodeException,
  InvalidPasswordException,
} from '@aws-sdk/client-cognito-identity-provider';
import { z } from 'zod';
import { logger } from '../../shared/powertools';
import { config } from '../../shared/config';

const cognito = new CognitoIdentityProviderClient({});

const ResetPasswordSchema = z.object({
  email: z.string().email(),
  code: z.string().min(1),
  newPassword: z.string().min(8),
});

const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const parseResult = ResetPasswordSchema.safeParse(event.body);
  if (!parseResult.success) {
    return res(400, { message: parseResult.error.issues[0].message });
  }

  const { email, code, newPassword } = parseResult.data;
  logger.info('Reset password attempt', { email });

  try {
    await cognito.send(new ConfirmForgotPasswordCommand({
      ClientId: config.userPoolClientId,
      Username: email,
      ConfirmationCode: code,
      Password: newPassword,
    }));

    logger.info('Password reset successful', { email });
    return res(200, { message: 'Password reset successful. You can now sign in.' });
  } catch (err) {
    if (err instanceof CodeMismatchException) {
      return res(400, { message: 'Invalid reset code.' });
    }
    if (err instanceof ExpiredCodeException) {
      return res(400, { message: 'Reset code has expired. Please request a new one.' });
    }
    if (err instanceof InvalidPasswordException) {
      return res(400, { message: (err as Error).message });
    }
    logger.error('Reset password failed', { email, error: String(err) });
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
