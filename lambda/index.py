# lambda/index.py
import json
import os
import boto3
import re  # 正規表現モジュールをインポート
from botocore.exceptions import ClientError

import urllib.request


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

# グローバル変数としてクライアントを初期化（初期値）
bedrock_client = None

# モデルID
# MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

def lambda_handler(event, context):
    try:
        # コンテキストから実行リージョンを取得し、クライアントを初期化
        # global bedrock_client
        # if bedrock_client is None:
        #     region = extract_region_from_arn(context.invoked_function_arn)
        #     bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        #     print(f"Initialized Bedrock client in region: {region}")

        print("Received event:", json.dumps(event))

        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")

        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])

        print("Processing message:", message)
        # print("Using model:", MODEL_ID)
        print("Using model from FastAPI.")

        # 会話履歴を使用
        messages = conversation_history.copy()

        # ユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": message
        })

        # FastAPIのリクエストペイロードを構築
        # 会話履歴を含める
        request_payload = {
            "prompt": message,
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.9
        }


        # print("Calling Bedrock invoke_model API with payload:", json.dumps(request_payload))
        print("Calling FastAPI with payload:", json.dumps(request_payload))

        # FastAPIのエンドポイントを呼び出す
        # FastAPIのURLを取得
        fastapi_url = os.environ.get("FASTAPI_URL", "").rstrip('/')
        endpoint_path = "generate"
        endpoint_url = f"{fastapi_url}/{endpoint_path}"

        # FastAPIのエンドポイントにPOSTリクエストを送信
        req = urllib.request.Request(endpoint_url, data=json.dumps(request_payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
        # レスポンスを取得
        try:
            with urllib.request.urlopen(req) as response:
                if response.getcode() != 200:
                    raise Exception(f"FastAPI request failed with status code: {response.getcode()}")
                response_body = json.loads(response.read())
                print("FastAPI response:", json.dumps(response_body, default=str))
        except urllib.error.HTTPError as e:
            print(f"HTTPError: {e.code} - {e.reason}")


        # 応答の検証
        if not response_body['generated_text']:
            raise Exception("No response content from the model")

        # アシスタントの応答を取得
        assistant_response = response_body['generated_text']

        # アシスタントの応答を会話履歴に追加
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })

        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }

    except Exception as error:
        print("Error:", str(error))

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
