# © 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer
# Agreement available at http://aws.amazon.com/agreement or other written
# agreement between Customer and either Amazon Web Services, Inc. or Amazon
# Web Services EMEA SARL or both.

import boto3
import os
import json
import logging
import uuid
import sys
from botocore.exceptions import ClientError
from datetime import datetime

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('botocore').setLevel(logging.CRITICAL)

session = boto3.Session()

scp_policy_count = os.environ['SCP_POLICY_COUNT']
scp_policy_1 = os.environ['DIRECT_ATTACH_SCP_POLICY_ID_1']
scp_policy_2 = os.getenv('DIRECT_ATTACH_SCP_POLICY_ID_2', 'None')
scp_policy_3 = os.getenv('DIRECT_ATTACH_SCP_POLICY_ID_3', 'None')
scp_policy_4 = os.getenv('DIRECT_ATTACH_SCP_POLICY_ID_4', 'None')
sns_topic = os.environ['SNS_TOPIC_ARN']
ou_id = os.getenv('OU_ID', 'None')

def scp_list():
    scp_policies = []
    if int(scp_policy_count) == 2:
        scp_policies.append(scp_policy_1)
        scp_policies.append(scp_policy_2)
    elif int(scp_policy_count) == 3:
        scp_policies.append(scp_policy_1)
        scp_policies.append(scp_policy_2)
        scp_policies.append(scp_policy_3)
        print(scp_policies)
    elif int(scp_policy_count) == 4:
        scp_policies.append(scp_policy_1)
        scp_policies.append(scp_policy_2)
        scp_policies.append(scp_policy_3)
        scp_policies.append(scp_policy_4)
        print(scp_policies)
    else:
        scp_policies.append(scp_policy_1)
    return scp_policies

def attach_policy(event, account_id, account_name):
    client = boto3.client('organizations')
    list_of_scp = scp_list()
    try:
        for scp in list_of_scp:
            response = client.attach_policy(
                PolicyId=scp,
                TargetId=account_id,
            )
            print(f'Successfully attached {scp} to {account_name} ({account_id})')
        format_event(list_of_scp, event, "succeeded")
    except Exception as e:
        format_event(list_of_scp, event, "failed")
        print(f"Could not attached SCP to {account_id}")

def format_event(list_of_scp, event, information):
    """ Creates message with information on Lambda success or failure """
    try:
        list_of_scps = '[%s]' % ', '.join(map(str, list_of_scp))
        
        time=event['detail']['eventTime'],
        ou=event['detail']['serviceEventDetails']['createManagedAccountStatus']['organizationalUnit']['organizationalUnitName'],
        ou_id=event['detail']['serviceEventDetails']['createManagedAccountStatus']['organizationalUnit']['organizationalUnitId'],
        account_name=event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountName'],
        account_id=event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountId'],
        scps=str(list_of_scps)[1:-1],
        success_or_failure=information
        
        details = {
            "creation_time":f"{time}",
            "account_name":f"{account_name}",
            "account_id":f"{account_id}",
            "scps":f"{scps}",
            "organizational_unit_name":f"{ou}",
            "organizational_unit_id":f"{ou}",
            "scp_attempt":f"{success_or_failure}"
        }

        detailedjson = json.dumps(details)
    except ClientError as error:
        LOGGER.info(f"Couldn't generate message to send to CloudWatch EventBridge")
    else:
        publish_to_eventbridge(detailedjson)

def publish_to_eventbridge(detailedjson):
    cw_events = boto3.client('events')
    try:
        response = cw_events.put_events(
            Entries=[
                {
                    'Source': 'attach-scp-lambda',
                    'DetailType': 'execution_results',
                    'Detail': f'{detailedjson}',
                    'EventBusName': 'default',
                }
            ])
        
    except ClientError as error:
        LOGGER.info(f"Couldn't send event to CloudWatch EventBridge")

def lambda_handler(event, context):
    LOGGER.info('REQUEST RECEIVED: {}'.format(json.dumps(event, default=str)))
    LOGGER.info("Lambda handler start")

    # Primary handler - takes event from master Lambda or life-cycle event
    if 'detail' in event and event['detail']['eventName'] == 'CreateManagedAccount':
        if event['detail']['serviceEventDetails']['createManagedAccountStatus']['state'] == 'SUCCEEDED':
            print('Sucessful event recieved.\n')
            account_id = event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountId']
            account_name = event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountName']
            ou = event['detail']['serviceEventDetails']['createManagedAccountStatus']['organizationalUnit']['organizationalUnitName']
            try:
                if event['detail']['serviceEventDetails']['createManagedAccountStatus']['organizationalUnit']['organizationalUnitName'] == ou_id:
                    attach_policy(event, account_id, account_name)
                else:
                    attach_policy(event, account_id, account_name)
            except:
                '''Unsucessful event recieved from Control Tower'''
                sys.exit('Unsucessful attmept to attach SCP to new account')
        else:
            '''Unsucessful event recieved from Control Tower'''
            sys.exit('Unsucessful event recieved from Control Tower')
    else:
        LOGGER.info(f'Control Tower Event Captured :{event}')
        sys.exit()
