import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import { DynamoDBDocumentClient, PutCommand } from '@aws-sdk/lib-dynamodb';
import { SFNClient, StartExecutionCommand } from '@aws-sdk/client-sfn';
import crypto from 'crypto';

const ddb = DynamoDBDocumentClient.from({
  marshallOptions: { removeUndefinedValues: true },
  unmarshallOptions: { wrapNumbers: false },
});
const sfnClient = new SFNClient({});

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  if (event.httpMethod === 'POST') {
    try {
      const body = JSON.parse(event.body || '{}');
      const { spec, model, project_path } = body;
      const job_id = crypto.randomUUID();
      const createdAt = new Date().toISOString();
      const updatedAt = new Date().toISOString();

      await ddb.send(new PutCommand({
        TableName: process.env.JOBS_TABLE_NAME,
        Item: {
          job_id,
          status: 'pending',
          spec,
          model,
          project_path,
          created_at: createdAt,
          updated_at: updatedAt,
        },
      }));

      const input = JSON.stringify({ job_id, spec, model, project_path, correction_rounds: 0 });
      await sfnClient.send(new StartExecutionCommand({
        stateMachineArn: process.env.STATE_MACHINE_ARN,
        input,
      }));

      return {
        statusCode: 202,
        body: JSON.stringify({ job_id }),
      };
    } catch (error) {
      console.error('Error submitting job:', error);
      return {
        statusCode: 500,
        body: JSON.stringify({ error: 'Internal Server Error' }),
      };
    }
  }

  if (event.httpMethod === 'GET') {
    try {
      const job_id = event.pathParameters?.job_id;
      if (!job_id) {
        return {
          statusCode: 400,
          body: JSON.stringify({ error: 'Missing job_id' }),
        };
      }

      const result = await ddb.send(new GetCommand({
        TableName: process.env.JOBS_TABLE_NAME,
        Key: { job_id },
      }));

      if (!result.Item) {
        return {
          statusCode: 404,
          body: JSON.stringify({ error: 'Job not found' }),
        };
      }

      return {
        statusCode: 200,
        body: JSON.stringify(result.Item),
      };
    } catch (error) {
      console.error('Error getting job:', error);
      return {
        statusCode: 500,
        body: JSON.stringify({ error: 'Internal Server Error' }),
      };
    }
  }

  return {
    statusCode: 405,
    body: JSON.stringify({ error: 'Method Not Allowed' }),
  };
};
