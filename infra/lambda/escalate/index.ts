import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const snsClient = new SNSClient({});

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  console.log('Received event:', JSON.stringify(event));

  try {
    await snsClient.send(new PublishCommand({
      TopicArn: process.env.ESCALATION_TOPIC_ARN,
      Message: JSON.stringify({ job_id: event.job_id, failure_reason: event.failure_reason }),
      Subject: 'Shepherd job escalated',
    }));

    return {
      statusCode: 200,
      body: JSON.stringify({ escalated: true }),
    };
  } catch (error) {
    console.error('Error escalating job:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal Server Error' }),
    };
  }
};
