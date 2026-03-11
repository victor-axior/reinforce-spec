#!/usr/bin/env pwsh
# Deploy ECS Fargate stack with RDS PostgreSQL

$ErrorActionPreference = "Stop"

$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"

& $aws cloudformation deploy `
  --stack-name "reinforce-spec-api" `
  --template-file "C:\Users\User\Documents\reinforce-spec\infra\aws\ecs-fargate\stack.yaml" `
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM `
  --region us-east-1 `
  --parameter-overrides `
    "ProjectName=reinforce-spec" `
    "VpcId=vpc-07927407137d03b0d" `
    "PublicSubnetIds=subnet-011cf4768098c1aaf,subnet-057ea20c563b5daaa" `
    "PrivateSubnetIds=subnet-05c7162a43ef2bc2f,subnet-070179eaeeb8560b3" `
    "ContainerImage=501000277888.dkr.ecr.us-east-1.amazonaws.com/axior-sandbox-preview:9e7f884" `
    "CertificateArn=arn:aws:acm:us-east-1:501000277888:certificate/8db6eb01-0203-4830-8b96-e18d6775f7e6" `
    "OpenRouterApiKeySecretArn=arn:aws:secretsmanager:us-east-1:501000277888:secret:reinforce-spec/openrouter-5rn9ru" `
    "DatabaseSecretArn=arn:aws:secretsmanager:us-east-1:501000277888:secret:reinforce-spec/database-url-vARJ9C" `
    "DomainName=axior.dev" `
    "ApiDomainName=reinforce.axior.dev"

Write-Host "Deployment complete!" -ForegroundColor Green
