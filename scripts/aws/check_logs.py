import boto3

logs = boto3.client('logs', region_name='us-east-1')
try:
    streams = logs.describe_log_streams(
        logGroupName='/ecs/reinforce-spec', 
        orderBy='LastEventTime', 
        descending=True, 
        limit=3
    )
    for stream in streams.get('logStreams', []):
        print(f"Stream: {stream['logStreamName']}")
        events = logs.get_log_events(
            logGroupName='/ecs/reinforce-spec', 
            logStreamName=stream['logStreamName'], 
            limit=50, 
            startFromHead=False
        )
        for event in events.get('events', []):
            print(event['message'])
        print('---')
except Exception as e:
    print(f'Error: {e}')
