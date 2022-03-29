"""
scanner.py
user: vhao
date: 03-27-2022

AWS Lambda entrypoint.
"""

import asyncio
import json
from scanner import start_scanning

def lambda_handler(event, context):
    asyncio.run(start_scanning())
    return {
        'statusCode': 200,
        'body': json.dumps('Scanning complete. Lambda finished.')
    }
