const getEnv = (key: string): string => {
  const value = process.env[key];
  if (!value) throw new Error(`Missing required environment variable: ${key}`);
  return value;
};

export const config = {
  userPoolClientId: getEnv('USER_POOL_CLIENT_ID'),
  userPoolId: getEnv('USER_POOL_ID'),
};
