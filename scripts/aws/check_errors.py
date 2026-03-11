#!/usr/bin/env python3
"""Check CloudWatch logs for errors in the ReinforceSpec API."""

import boto3
from datetime import datetime

logs = boto3.client('logs', region_name='us-east-1')

# Get the most recent log streams
streams = logs.describe_log_streams(
    logGroupName='/ecs/reinforce-spec',
    orderBy='LastEventTime',
    descending=True,
    limit=3
)

print('=== CloudWatch Logs - Full Error Analysis ===\n')

for stream in streams.get('logStreams', []):
    stream_name = stream['logStreamName']
    print(f'Stream: {stream_name}')
    print('=' * 70)
    
    # Get all recent log events
    events = logs.get_log_events(
        logGroupName='/ecs/reinforce-spec',
        logStreamName=stream_name,
        limit=200,
        startFromHead=False
    )
    
    # Print events that are errors or tracebacks
    in_traceback = False
    for event in events.get('events', []):
        msg = event['message']
        ts = datetime.fromtimestamp(event['timestamp']/1000).strftime('%H:%M:%S')
        
        # Detect start of traceback
        if 'Traceback' in msg:
            in_traceback = True
        
        # Print if in traceback or contains error keywords
        if in_traceback or any(x in msg.lower() for x in ['error', 'exception', 'failed']):
            print(f'[{ts}] {msg}')
        
        # Detect end of traceback (error line)
        if in_traceback and ('Error:' in msg or 'Exception:' in msg):
            in_traceback = False
            print()  # Add blank line after error
    
    print()
