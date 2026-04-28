import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  console.log('Received event:', JSON.stringify(event));

  return {
    statusCode: 200,
    body: JSON.stringify({
      ...event,
      approved: true,
      review_notes: 'stub — always approves',
    }),
  };
};
