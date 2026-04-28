import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const snsClient = new SNSClient({});

export const handler = async (event: Record<string, unknown>): Promise<Record<string, unknown>> => {
  console.log('escalate invoked:', JSON.stringify(event));
  await snsClient.send(new PublishCommand({
    TopicArn: process.env.ESCALATION_TOPIC_ARN,
    Message: JSON.stringify({ job_id: event['job_id'], failure_reason: event['failure_reason'] }),
    Subject: 'Shepherd job escalated',
  }));
  return { escalated: true };
};
