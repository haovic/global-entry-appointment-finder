"""
scanner_lambdas_utils.py
user: vhao
date: 03-27-2022

NOTE: This file should only be imported when USING_AWS_LAMBDA=True.

Helper functions for when the scanner is run on AWS lambdas.

These functions mostly help abstract reading/writing from /tmp or S3, as
minimizing the necessary S3 calls will greatly reduce potential costs of
running this script on the Amazon suite. This is only necessary for files
which must be mutable. Any static files can be read from the working 
directory.

From the AWS docs: 
https://aws.amazon.com/blogs/compute/choosing-between-aws-lambda-data-storage-options-in-web-apps/

The Lambda execution environment provides a file system for your code to use at 
/tmp. This space has a fixed size of 512 MB. The same Lambda execution 
environment may be reused by multiple Lambda invocations to optimize 
performance. The /tmp area is preserved for the lifetime of the execution 
environment and provides a transient cache for data between invocations. Each 
time a new execution environment is created, this area is deleted.

Consequently, this is intended as an ephemeral storage area. While functions 
may cache data here between invocations, it should be used only for data needed 
by code in a single invocation. It's not a place to store data permanently, and 
is better-used to support operations required by your code.

S3 Pricing: https://aws.amazon.com/s3/pricing/
As part of the AWS Free Tier, you can get ... 20,000 GET Requests; 2,000 PUT, 
COPY, POST, or LIST Requests; and 100 GB of Data Transfer Out each month.
"""

import logging

import boto3
import os
import sys
import traceback
from scanner_constants import USING_AWS_LAMBDA, S3_BUCKET, S3_PATH
from scanner_logger import getScannerLogger


logger = getScannerLogger(__name__)
s3 = boto3.client('s3')


"""
Desc: Tries to read from /tmp if file exists. Otherwise reads from S3. If that 
also fails, then this function rethrows the exception.
"""
def lambda_read(path: str) -> str:
    try:
        local_path = os.path.join(os.path.sep, "tmp", path)
        with open(local_path, "r") as f:
            data = f.read()
            logger.info(
                f"Successfully read {local_path} from lambda "
                "local storage"
            )
            return data
    except:
        logger.info(
            f"Failed to read {local_path} from lambda local storage, "
            "falling back on S3"
        )

    # Read from S3 instead
    s3_path = os.path.join(S3_PATH, path)
    try:
        data = s3.get_object(Bucket=S3_BUCKET, Key=s3_path)
        return data['Body'].read()
    except Exception as e:
        logger.warning(
            f"Unable to read {s3_path} from S3. Does the file not exist yet?"
        )
        raise e


"""
Args:
    writethrough:   When True, writes to both /tmp dir and S3. When False,
                    only writes to /temp. Does not throw when writethrough is
                    False.
"""
def lambda_write(path: str, bytes: str, writethrough: bool = True) -> None:
    local_path = os.path.join(os.path.sep, "tmp", path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(local_path, "w") as f:
            f.write(bytes)
    except Exception as e:
        # Swallow exception as we don't really care if we manage
        # to write to ephemeral storage or not
        logger.warning(
            "".join(traceback.format_exception(None, e, e.__traceback__))
        )
        logger.warning(
            f"Unable to write {local_path} to lambda local storage"
        )

    if writethrough:
        s3_path = os.path.join(S3_PATH, path)
        try:
            _ = s3.put_object(Bucket=S3_BUCKET, Key=s3_path, Body=bytes)
        except Exception as e:
            logger.warning(f"Unable to write {s3_path} to S3")
            raise e
