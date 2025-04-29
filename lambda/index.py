# lambda/index.py
import json
import os
import boto3
import re  # 正規表現モジュールをインポート
import urllib.request
from botocore.exceptions import ClientError


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

# グローバル変数としてクライアントを初期化（初期値）
# bedrock_client = None
fastapi_endpoint = "https://f749-35-194-186-141.ngrok-free.app/generate"

# モデルID
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

def lambda_handler(event, context):
    try:
        # コンテキストから実行リージョンを取得し、クライアントを初期化
        # global bedrock_client
        # if bedrock_client is None:
            # region = extract_region_from_arn(context.invoked_function_arn)
            # bedrock_client = boto3.client('bedrock-runtime', region_name=region)
            # print(f"Initialized Bedrock client in region: {region}")
        
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
        print("Using model:", MODEL_ID)
        
        # 会話履歴を使用
        messages = conversation_history.copy()
        
        # ユーザーメッセージを追加
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Nova Liteモデル用のリクエストペイロードを構築
        # 会話履歴を含める
        messages = []
        for msg in messages:
            if msg["role"] == "user":
                messages.append({
                    "role": "user",
                    "content": [{"text": msg["content"]}]
                })
            elif msg["role"] == "assistant":
                messages.append({
                    "role": "assistant", 
                    "content": [{"text": msg["content"]}]
                })
        
        # invoke_model用のリクエストペイロード
        # request_payload = {
            # "messages": bedrock_messages,
            # "inferenceConfig": {
                # "maxTokens": 512,
                # "stopSequences": [],
                # "temperature": 0.7,
                # "topP": 0.9
            # }
        # }

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": messages,
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        data = json.dumps(payload).encode("utf-8")
        
        print("Calling FastAPI invoke_model API with payload:", json.dumps(request_payload))
        
        # invoke_model APIを呼び出し
        # response = bedrock_client.invoke_model(
            # modelId=MODEL_ID,
            # body=json.dumps(request_payload),
            # contentType="application/json"
        # )

        req = urllib.request.Request(
            FASTAPI_URL,
            headers=headers,
            data=data,
            method="POST"
        )

        try: 
            with urllib.request.urlopen(req) as response:
                response_body = json.loads(response.read().decode())

            # if response.status_code != 200:
                # error_detail = response.json()
                # raise Exception(f"API error {response.status_code}: {json.dumps(error_detail, ensure_ascii=False)}")
        
            # レスポンスを解析
            # response_body = response.json()
            print("FastAPI response:", json.dumps(response_body, default=str))
        
            # 応答の検証
            # if not response_body.get('output') or not response_body['output'].get('message') or not response_body['output']['message'].get('content'):
                # raise Exception("No response content from the model")
            if 'generated_text' not in response_body or not response_body['generated_text']:
                raise Exception("No generated_text returned from the model")
        
            # アシスタントの応答を取得
            # assistant_response = response_body['output']['message']['content'][0]['text']
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
            
        except urllib.error.HTTPError as e:
            error_detail = e.read().decode()
            if e.getcode() == 422:  # 422エラーを処理
                # 422エラーの詳細を解析
                error_response = json.loads(error_detail)
                error_messages = error_response.get("detail", [])
                error_msg = ", ".join([f"{err['loc'][0]}: {err['msg']}" for err in error_messages])
                raise Exception(f"API error 422: {error_msg}")
            else:
                raise Exception(f"API error {e.getcode()}: {error_detail}")
        
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
