#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ShepherdPipelineStack } from '../lib/shepherd-pipeline-stack';

const app = new cdk.App();
new ShepherdPipelineStack(app, 'ShepherdPipelineStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
