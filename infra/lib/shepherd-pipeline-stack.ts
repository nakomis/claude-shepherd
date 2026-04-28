import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export class ShepherdPipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const jobsTable = new dynamodb.Table(this, 'JobsTable', {
      tableName: 'shepherd-jobs',
      partitionKey: { name: 'job_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const artifactsBucket = new s3.Bucket(this, 'ArtifactsBucket', {
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const ollamaDlq = new sqs.Queue(this, 'OllamaDlq', {
      queueName: 'shepherd-ollama-dlq',
    });

    const ollamaQueue = new sqs.Queue(this, 'OllamaQueue', {
      queueName: 'shepherd-ollama-queue',
      visibilityTimeout: cdk.Duration.seconds(900),
      deadLetterQueue: { queue: ollamaDlq, maxReceiveCount: 3 },
    });

    const escalationTopic = new sns.Topic(this, 'EscalationTopic', {
      topicName: 'shepherd-escalations',
    });

    const ssmPolicy = new iam.PolicyStatement({
      actions: ['ssm:GetParameter', 'ssm:GetParameters'],
      resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter/shepherd/*`],
    });

    const makeFn = (
      id: string,
      name: string,
      dir: string,
      timeout: cdk.Duration,
      env: Record<string, string>,
    ): lambda.Function => {
      const fn = new lambda.Function(this, id, {
        functionName: name,
        runtime: lambda.Runtime.NODEJS_20_X,
        handler: 'index.handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', dir)),
        timeout,
        environment: {
          JOBS_TABLE_NAME: jobsTable.tableName,
          ARTIFACTS_BUCKET_NAME: artifactsBucket.bucketName,
          ...env,
        },
      });
      jobsTable.grantReadWriteData(fn);
      fn.addToRolePolicy(ssmPolicy);
      return fn;
    };

    const submitJobFn = makeFn('SubmitJobFn', 'shepherd-submit-job', 'submit-job', cdk.Duration.seconds(30), {
      STATE_MACHINE_ARN: 'PENDING',
    });
    artifactsBucket.grantRead(submitJobFn);

    const generateFn = makeFn('GenerateFn', 'shepherd-generate', 'generate', cdk.Duration.seconds(900), {
      OLLAMA_QUEUE_URL: ollamaQueue.queueUrl,
      GENERATE_MODEL_SSM_PATH: '/shepherd/generate/model',
    });
    artifactsBucket.grantReadWrite(generateFn);
    ollamaQueue.grantSendMessages(generateFn);

    const compileFn = makeFn('CompileFn', 'shepherd-compile-gate', 'compile-gate', cdk.Duration.seconds(600), {
      GITHUB_TOKEN_SSM_PATH: '/shepherd/github/token',
    });
    artifactsBucket.grantReadWrite(compileFn);

    const reviewFn = makeFn('ReviewFn', 'shepherd-review', 'review', cdk.Duration.seconds(300), {
      REVIEW_MODEL_SSM_PATH: '/shepherd/review/model',
    });
    artifactsBucket.grantReadWrite(reviewFn);

    const mergeFn = makeFn('MergeFn', 'shepherd-merge', 'merge', cdk.Duration.seconds(60), {
      GITHUB_TOKEN_SSM_PATH: '/shepherd/github/token',
    });

    const escalateFn = makeFn('EscalateFn', 'shepherd-escalate', 'escalate', cdk.Duration.seconds(30), {
      ESCALATION_TOPIC_ARN: escalationTopic.topicArn,
    });
    escalationTopic.grantPublish(escalateFn);

    // Step Functions — escalateTask declared first as it is referenced by addCatch on other states
    const escalateTask = new tasks.LambdaInvoke(this, 'Escalate', {
      lambdaFunction: escalateFn,
      payloadResponseOnly: true,
    });

    const mergeTask = new tasks.LambdaInvoke(this, 'Merge', {
      lambdaFunction: mergeFn,
      payloadResponseOnly: true,
    });

    const reviewTask = new tasks.LambdaInvoke(this, 'Review', {
      lambdaFunction: reviewFn,
      payloadResponseOnly: true,
    }).addCatch(escalateTask, { errors: ['States.ALL'] });

    const compileTask = new tasks.LambdaInvoke(this, 'CompileGate', {
      lambdaFunction: compileFn,
      payloadResponseOnly: true,
    }).addCatch(escalateTask, { errors: ['States.ALL'] });

    const generateTask = new tasks.LambdaInvoke(this, 'Generate', {
      lambdaFunction: generateFn,
      payloadResponseOnly: true,
    }).addCatch(escalateTask, { errors: ['States.ALL'] });

    const reviewChoice = new sfn.Choice(this, 'ReviewChoice')
      .when(sfn.Condition.booleanEquals('$.approved', true), mergeTask)
      .when(sfn.Condition.numberGreaterThanEquals('$.correction_rounds', 3), escalateTask)
      .otherwise(generateTask);

    generateTask.next(compileTask).next(reviewTask).next(reviewChoice);

    const stateMachine = new sfn.StateMachine(this, 'ShepherdPipeline', {
      definitionBody: sfn.DefinitionBody.fromChainable(generateTask),
      stateMachineName: 'shepherd-pipeline',
      timeout: cdk.Duration.hours(4),
    });

    stateMachine.grantStartExecution(submitJobFn);
    submitJobFn.addEnvironment('STATE_MACHINE_ARN', stateMachine.stateMachineArn);

    const api = new apigateway.RestApi(this, 'ShepherdApi', {
      restApiName: 'shepherd-api',
      description: 'Shepherd drone pipeline API',
    });
    const jobsResource = api.root.addResource('jobs');
    const submitIntegration = new apigateway.LambdaIntegration(submitJobFn);
    jobsResource.addMethod('POST', submitIntegration);
    jobsResource.addResource('{job_id}').addMethod('GET', submitIntegration);

    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
    new cdk.CfnOutput(this, 'JobsTableName', { value: jobsTable.tableName });
    new cdk.CfnOutput(this, 'ArtifactsBucketName', { value: artifactsBucket.bucketName });
  }
}
