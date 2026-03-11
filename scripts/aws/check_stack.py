import boto3
import sys

def check_ecs_service_logs():
    """Check ECS service events and task failures"""
    try:
        ecs = boto3.client('ecs', region_name='us-east-1')
        logs = boto3.client('logs', region_name='us-east-1')
        
        # Try to find the cluster and service
        print("\n=== ECS Service/Task Analysis ===\n")
        
        # List all clusters
        clusters = ecs.list_clusters()
        for cluster_arn in clusters.get('clusterArns', []):
            if 'reinforce-spec' in cluster_arn:
                print(f"Found cluster: {cluster_arn.split('/')[-1]}")
                
                # List services
                services = ecs.list_services(cluster=cluster_arn, maxResults=10)
                for service_arn in services.get('serviceArns', []):
                    print(f"\nService: {service_arn.split('/')[-1]}")
                    
                    # Get service events
                    service_desc = ecs.describe_services(
                        cluster=cluster_arn,
                        services=[service_arn]
                    )
                    
                    for svc in service_desc.get('services', []):
                        print(f"  Status: {svc.get('status')}")
                        print(f"  Running: {svc.get('runningCount')}")
                        print(f"  Desired: {svc.get('desiredCount')}")
                        print("\n  Recent Events:")
                        for event in svc.get('events', [])[:5]:
                            print(f"    {event['createdAt'].strftime('%H:%M:%S')} - {event['message']}")
                
                # List recent tasks (including stopped)
                tasks = ecs.list_tasks(cluster=cluster_arn, desiredStatus='STOPPED', maxResults=5)
                if tasks.get('taskArns'):
                    print("\n  Recent Stopped Tasks:")
                    task_details = ecs.describe_tasks(cluster=cluster_arn, tasks=tasks['taskArns'])
                    for task in task_details.get('tasks', []):
                        print(f"\n    Task: {task['taskArn'].split('/')[-1]}")
                        print(f"    Last Status: {task.get('lastStatus')}")
                        print(f"    Stopped Reason: {task.get('stoppedReason', 'N/A')}")
                        for container in task.get('containers', []):
                            print(f"    Container: {container.get('name')}")
                            print(f"      Exit Code: {container.get('exitCode', 'N/A')}")
                            print(f"      Reason: {container.get('reason', 'N/A')}")
        
        # Try to get CloudWatch logs for reinforce-spec
        print("\n=== CloudWatch Logs (last 20 entries) ===\n")
        try:
            log_group = '/ecs/reinforce-spec'
            streams = logs.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=3
            )
            for stream in streams.get('logStreams', []):
                print(f"Log stream: {stream['logStreamName']}")
                events = logs.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream['logStreamName'],
                    limit=20,
                    startFromHead=False
                )
                for event in events.get('events', []):
                    print(f"  {event['message'][:200]}")
        except Exception as e:
            print(f"Could not fetch logs: {e}")
            
    except Exception as e:
        print(f"Error checking ECS: {e}")

try:
    cf = boto3.client('cloudformation', region_name='us-east-1')
    events = cf.describe_stack_events(StackName='reinforce-spec-api')
    
    print(f"{'Timestamp':<20} | {'Resource':<40} | {'Status':<25} | {'Reason'}")
    print("-" * 150)
    
    # Show all events, especially failures
    for event in events['StackEvents']:
        timestamp = event['Timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        resource = event['LogicalResourceId'][:40]
        status = event['ResourceStatus']
        reason = event.get('ResourceStatusReason', '')
        
        # Highlight failures
        if 'FAILED' in status or 'ROLLBACK' in status:
            print(f"\n*** {timestamp:<20} | {resource:<40} | {status:<25} ***")
            if reason:
                print(f"    REASON: {reason}\n")
        else:
            print(f"{timestamp:<20} | {resource:<40} | {status:<25} | {reason}")
        
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# Run ECS analysis
check_ecs_service_logs()
