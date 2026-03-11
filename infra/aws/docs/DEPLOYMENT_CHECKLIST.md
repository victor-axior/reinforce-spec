# AWS Fargate Deployment Checklist

## Pre-Deployment Setup

### 1. AWS Infrastructure Prerequisites

- [ ] **VPC Configuration**
  ```bash
  # You need a VPC with:
  # - At least 2 public subnets (for ALB) in different AZs
  # - At least 2 private subnets (for ECS tasks) in different AZs
  
  # Get your VPC ID:
  aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,Tags[?Key==`Name`].Value|[0]]' --output table
  
  # Get subnet IDs:
  aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-xxxxx" \
    --query 'Subnets[*].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch,Tags[?Key==`Name`].Value|[0]]' \
    --output table
  ```
  
  **Record**:
  - VPC ID: `vpc-_________________`
  - Public Subnet 1: `subnet-_________________` (AZ: ________)
  - Public Subnet 2: `subnet-_________________` (AZ: ________)
  - Private Subnet 1: `subnet-_________________` (AZ: ________)
  - Private Subnet 2: `subnet-_________________` (AZ: ________)

---

### 2. ACM Certificate

- [ ] **Request or import SSL/TLS certificate**
  ```bash
  # Option A: Request new certificate (requires DNS validation)
  aws acm request-certificate \
    --domain-name api.example.com \
    --validation-method DNS \
    --region us-east-1
  
  # Option B: Use existing certificate
  aws acm list-certificates --region us-east-1
  ```
  
  **Record**:
  - Certificate ARN: `arn:aws:acm:us-east-1:____________:certificate/_______________`

---

### 3. Secrets Manager Setup

- [ ] **Create secret for OpenRouter API key**
  ```bash
  # Create the secret
  aws secretsmanager create-secret \
    --name reinforce-spec/openrouter-api-key \
    --description "OpenRouter API key for ReinforceSpec" \
    --secret-string "$OPENROUTER_API_KEY" \
    --region us-east-1
  
  # Get the ARN
  aws secretsmanager describe-secret \
    --secret-id reinforce-spec/openrouter-api-key \
    --region us-east-1 \
    --query 'ARN' \
    --output text
  ```
  
  **Record**:
  - Secret ARN: `arn:aws:secretsmanager:us-east-1:____________:secret:_______________`

---

### 4. Optional: Route53 Hosted Zone

- [ ] **Configure custom domain (skip if using ALB DNS directly)**
  ```bash
  # List hosted zones
  aws route53 list-hosted-zones --query 'HostedZones[*].[Id,Name]' --output table
  ```
  
  **Record** (if using custom domain):
  - Hosted Zone ID: `Z_______________`
  - API Domain Name: `api.example.com`

---

### 5. Configure Environment Variables

- [ ] **Update `.env` file in repository root**
  ```bash
  # Copy example and edit
  cp .env.example .env
  
  # Edit .env with your values:
  RS_AWS_VPC_ID=vpc-xxxxx
  RS_AWS_PUBLIC_SUBNETS=subnet-aaa,subnet-bbb
  RS_AWS_PRIVATE_SUBNETS=subnet-ccc,subnet-ddd
  RS_AWS_CERTIFICATE_ARN=arn:aws:acm:...
  RS_AWS_OPENROUTER_SECRET_ARN=arn:aws:secretsmanager:...
  
  # Optional:
  RS_AWS_HOSTED_ZONE_ID=Z123456
  RS_AWS_API_DOMAIN_NAME=api.example.com
  RS_AWS_REGION=us-east-1
  RS_AWS_STACK_NAME=reinforce-spec-api
  RS_AWS_DESIRED_COUNT=2
  RS_AWS_MIN_COUNT=2
  RS_AWS_MAX_COUNT=6
  RS_AWS_TASK_CPU=1024
  RS_AWS_TASK_MEMORY=2048
  RS_AWS_WORKERS=2
  RS_AWS_LOG_LEVEL=info
  ```

---

### 6. AWS CLI Configuration

- [ ] **Verify AWS credentials and region**
  ```bash
  # Check current configuration
  aws sts get-caller-identity
  aws configure get region
  
  # If not configured:
  aws configure
  # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output (json)
  ```
  
  **Verify**:
  - Account ID: ____________
  - Region: ____________
  - IAM User/Role: ____________

---

## Deployment

### 7. Build and Deploy

- [ ] **Run deployment script**
  ```bash
  cd /path/to/reinforce-spec
  
  # Dry run (validate parameters)
  ./scripts/aws/deploy_ecs_fargate.sh --help
  
  # Deploy with .env values
  ./scripts/aws/deploy_ecs_fargate.sh \
    --vpc-id $RS_AWS_VPC_ID \
    --public-subnets $RS_AWS_PUBLIC_SUBNETS \
    --private-subnets $RS_AWS_PRIVATE_SUBNETS \
    --certificate-arn $RS_AWS_CERTIFICATE_ARN \
    --openrouter-secret-arn $RS_AWS_OPENROUTER_SECRET_ARN
  
  # With custom domain:
  ./scripts/aws/deploy_ecs_fargate.sh \
    --vpc-id $RS_AWS_VPC_ID \
    --public-subnets $RS_AWS_PUBLIC_SUBNETS \
    --private-subnets $RS_AWS_PRIVATE_SUBNETS \
    --certificate-arn $RS_AWS_CERTIFICATE_ARN \
    --openrouter-secret-arn $RS_AWS_OPENROUTER_SECRET_ARN \
    --hosted-zone-id $RS_AWS_HOSTED_ZONE_ID \
    --api-domain $RS_AWS_API_DOMAIN_NAME
  ```
  
  **Expected Duration**: 10-15 minutes
  - Docker build + push: 3-5 min
  - CloudFormation stack creation: 5-10 min

---

### 8. Verify Deployment

- [ ] **Check CloudFormation stack status**
  ```bash
  aws cloudformation describe-stacks \
    --stack-name reinforce-spec-api \
    --query 'Stacks[0].StackStatus' \
    --output text
  
  # Should show: CREATE_COMPLETE or UPDATE_COMPLETE
  ```

- [ ] **Get stack outputs**
  ```bash
  aws cloudformation describe-stacks \
    --stack-name reinforce-spec-api \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table
  ```
  
  **Record**:
  - ALB DNS: ____________________________________________
  - HTTPS URL: ____________________________________________
  - Custom Domain URL (if configured): ____________________________________________

---

### 9. Health Check Validation

- [ ] **Test health endpoint**
  ```bash
  # Get the ALB URL
  ALB_URL=$(aws cloudformation describe-stacks \
    --stack-name reinforce-spec-api \
    --query 'Stacks[0].Outputs[?OutputKey==`HttpsUrl`].OutputValue' \
    --output text)
  
  # Test health endpoint
  curl -v $ALB_URL/v1/health
  
  # Expected response:
  # {"status":"ok","version":"0.1.0","uptime_seconds":123}
  ```

- [ ] **Test readiness endpoint**
  ```bash
  curl -v $ALB_URL/v1/health/ready
  
  # Expected response:
  # {"status":"ready","version":"0.1.0","uptime_seconds":123}
  ```

---

### 10. ECS Service Validation

- [ ] **Check ECS service status**
  ```bash
  aws ecs describe-services \
    --cluster reinforce-spec-cluster \
    --services reinforce-spec-service \
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
    --output table
  
  # Running should equal Desired (usually 2)
  ```

- [ ] **List running tasks**
  ```bash
  aws ecs list-tasks \
    --cluster reinforce-spec-cluster \
    --service-name reinforce-spec-service
  
  # Get task details
  TASK_ARN=$(aws ecs list-tasks \
    --cluster reinforce-spec-cluster \
    --service-name reinforce-spec-service \
    --query 'taskArns[0]' \
    --output text)
  
  aws ecs describe-tasks \
    --cluster reinforce-spec-cluster \
    --tasks $TASK_ARN \
    --query 'tasks[0].{Status:lastStatus,Health:healthStatus,DesiredStatus:desiredStatus}'
  ```

---

### 11. CloudWatch Logs Check

- [ ] **Verify logs are flowing**
  ```bash
  # Tail logs in real-time
  aws logs tail /ecs/reinforce-spec --follow
  
  # Search for startup success message
  aws logs filter-log-events \
    --log-group-name /ecs/reinforce-spec \
    --filter-pattern "server_started" \
    --max-items 5
  ```

---

### 12. EFS Mount Verification

- [ ] **Check EFS filesystem status**
  ```bash
  # Get EFS ID from stack
  EFS_ID=$(aws cloudformation describe-stacks \
    --stack-name reinforce-spec-api \
    --query 'Stacks[0].Outputs[?OutputKey==`FileSystemId`].OutputValue' \
    --output text)
  
  # Check filesystem
  aws efs describe-file-systems --file-system-id $EFS_ID
  
  # Check mount targets
  aws efs describe-mount-targets --file-system-id $EFS_ID
  ```

- [ ] **Verify EFS is accessible from tasks**
  ```bash
  # Enable ECS Exec (if not already enabled)
  aws ecs update-service \
    --cluster reinforce-spec-cluster \
    --service reinforce-spec-service \
    --enable-execute-command
  
  # Wait a few seconds, then get a task ID
  TASK_ID=$(aws ecs list-tasks \
    --cluster reinforce-spec-cluster \
    --service-name reinforce-spec-service \
    --query 'taskArns[0]' \
    --output text | awk -F/ '{print $NF}')
  
  # Exec into container and check EFS mount
  aws ecs execute-command \
    --cluster reinforce-spec-cluster \
    --task $TASK_ID \
    --container api \
    --interactive \
    --command "ls -la /app/data"
  
  # You should see:
  # drwxr-xr-x 3 appuser appuser 4096 ... policies
  # drwxr-xr-x 2 appuser appuser 4096 ... db
  ```

---

## Post-Deployment Monitoring

### 13. Set Up CloudWatch Alarms

- [ ] **Create alarms for key metrics**
  ```bash
  # High CPU alarm
  aws cloudwatch put-metric-alarm \
    --alarm-name reinforce-spec-high-cpu \
    --alarm-description "Alert when CPU > 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=ServiceName,Value=reinforce-spec-service Name=ClusterName,Value=reinforce-spec-cluster
  
  # High memory alarm
  aws cloudwatch put-metric-alarm \
    --alarm-name reinforce-spec-high-memory \
    --alarm-description "Alert when memory > 80%" \
    --metric-name MemoryUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=ServiceName,Value=reinforce-spec-service Name=ClusterName,Value=reinforce-spec-cluster
  
  # Unhealthy targets alarm
  aws cloudwatch put-metric-alarm \
    --alarm-name reinforce-spec-unhealthy-targets \
    --alarm-description "Alert when targets are unhealthy" \
    --metric-name UnHealthyHostCount \
    --namespace AWS/ApplicationELB \
    --statistic Average \
    --period 60 \
    --evaluation-periods 2 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold
  ```

---

### 14. Monitor for First 24 Hours

- [ ] **Watch ECS task stability**
  ```bash
  # Check task status every 5 minutes
  watch -n 300 'aws ecs describe-services \
    --cluster reinforce-spec-cluster \
    --services reinforce-spec-service \
    --query "services[0].{Running:runningCount,Desired:desiredCount}"'
  ```

- [ ] **Monitor EFS performance**
  ```bash
  # Check EFS I/O percentage (should stay < 80%)
  aws cloudwatch get-metric-statistics \
    --namespace AWS/EFS \
    --metric-name PercentIOLimit \
    --dimensions Name=FileSystemId,Value=$EFS_ID \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Maximum \
    --query 'Datapoints[*].[Timestamp,Maximum]' \
    --output table
  ```

- [ ] **Check CloudWatch Insights metrics**
  ```bash
  # View Container Insights dashboard
  echo "View at: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#container-insights:performance/ECS?~(query~(controls~(CW*3a*3aECS.cluster~(~'reinforce-spec-cluster))))"
  ```

---

### 15. Load Testing (Optional)

- [ ] **Run basic load test**
  ```bash
  # Install hey (HTTP load testing tool)
  # macOS: brew install hey
  # Linux: go install github.com/rakyll/hey@latest
  
  # Test health endpoint
  hey -n 1000 -c 10 -m GET $ALB_URL/v1/health
  
  # Test specs endpoint with minimal payload
  cat > test_payload.json <<'EOF'
  {
    "candidates": [
      {"content": "# Spec A\nMinimal test spec"},
      {"content": "# Spec B\nAnother test spec"}
    ],
    "selection_method": "scoring_only"
  }
  EOF
  
  hey -n 50 -c 2 -m POST \
    -H "Content-Type: application/json" \
    -D test_payload.json \
    $ALB_URL/v1/specs
  
  # Monitor auto-scaling during load test
  watch -n 10 'aws ecs describe-services \
    --cluster reinforce-spec-cluster \
    --services reinforce-spec-service \
    --query "services[0].{Running:runningCount,Desired:desiredCount}"'
  ```

---

## Troubleshooting

### Common Issues

#### Issue 1: Tasks failing health checks

```bash
# Check logs for errors
aws logs tail /ecs/reinforce-spec --since 30m --filter-pattern "ERROR"

# Common causes:
# - EFS mount not accessible (check mount targets)
# - Secrets Manager permission denied (check IAM role)
# - OpenRouter API key invalid (verify secret value)
```

#### Issue 2: Tasks keep restarting

```bash
# Get stopped task details
aws ecs list-tasks \
  --cluster reinforce-spec-cluster \
  --desired-status STOPPED \
  --max-items 1

# Describe stopped task
STOPPED_TASK=$(aws ecs list-tasks \
  --cluster reinforce-spec-cluster \
  --desired-status STOPPED \
  --query 'taskArns[0]' \
  --output text)

aws ecs describe-tasks \
  --cluster reinforce-spec-cluster \
  --tasks $STOPPED_TASK \
  --query 'tasks[0].{Reason:stoppedReason,Containers:containers[*].{Name:name,Reason:reason}}'
```

#### Issue 3: Cannot write to EFS

```bash
# Exec into container
aws ecs execute-command \
  --cluster reinforce-spec-cluster \
  --task <task-id> \
  --container api \
  --interactive \
  --command "/bin/sh"

# Inside container:
id  # Should show: uid=10001(appuser)
ls -la /app/data  # Should show: drwxr-xr-x 3 appuser appuser
touch /app/data/test  # Should succeed
```

#### Issue 4: High latency

```bash
# Check ALB target response time
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --query 'Datapoints[*].[Timestamp,Average,Maximum]' \
  --output table
```

---

## Rollback Procedure

If deployment fails or causes issues:

```bash
# Option 1: Rollback to previous task definition
aws ecs update-service \
  --cluster reinforce-spec-cluster \
  --service reinforce-spec-service \
  --task-definition reinforce-spec-task:1  # Replace with previous revision

# Option 2: Delete stack and redeploy
aws cloudformation delete-stack --stack-name reinforce-spec-api
# Wait for deletion to complete
aws cloudformation wait stack-delete-complete --stack-name reinforce-spec-api
# Then redeploy with working configuration
```

---

## Cleanup (Development/Testing)

To completely remove the deployment:

```bash
# Delete CloudFormation stack (deletes all resources except EFS data)
aws cloudformation delete-stack --stack-name reinforce-spec-api

# Wait for completion
aws cloudformation wait stack-delete-complete --stack-name reinforce-spec-api

# Delete EFS backups (if AWS Backup was configured)
aws backup list-recovery-points-by-backup-vault --backup-vault-name Default

# Delete ECR images (optional)
aws ecr batch-delete-image \
  --repository-name reinforce-spec \
  --image-ids imageTag=latest

# Delete Secrets Manager secret
aws secretsmanager delete-secret \
  --secret-id reinforce-spec/openrouter-api-key \
  --force-delete-without-recovery
```

---

## Cost Estimation

**Monthly costs (us-east-1, approximate)**:

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| Fargate | 2 tasks × 1 vCPU × 2GB × 730 hours | ~$60 |
| ALB | 1 ALB + data transfer (1TB) | ~$35 |
| EFS | 10GB storage + I/O | ~$5 |
| CloudWatch Logs | 5GB ingestion + storage | ~$3 |
| Secrets Manager | 1 secret | ~$0.40 |
| **Total** | | **~$103/month** |

**Cost optimization**:
- Use Fargate Spot (70% savings): ~$35/month
- Reduce to 1 task in dev: ~$50/month
- Use EFS Infrequent Access: ~$4/month

---

## Next Steps

After successful deployment:

1. **Set up CI/CD** (GitHub Actions)
2. **Configure monitoring dashboard** (CloudWatch)
3. **Enable AWS Backup** for EFS
4. **Set up ECR scanning**
5. **Document runbooks** for common operations
6. **Schedule production deployment** window

---

**Checklist Complete**: _____ / _____ items

**Deployment Date**: __________________  
**Deployed By**: __________________  
**Stack Name**: __________________  
**Region**: __________________  
**ALB URL**: __________________
