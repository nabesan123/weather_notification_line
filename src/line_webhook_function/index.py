import json
import boto3
import os
import requests
from datetime import datetime, timedelta

ssm = boto3.client('ssm')

def get_ssm_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

LINE_ACCESS_TOKEN = get_ssm_parameter(os.environ['LINE_ACCESS_TOKEN_SSM'])
OPENWEATHERMAP_API_KEY = get_ssm_parameter(os.environ['OPENWEATHERMAP_API_KEY_SSM'])
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

CITIES = ['Tokyo', 'Kyoto', 'Sapporo', 'Osaka', 'Fukuoka']

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    try:
        body = json.loads(event['body'])
        for event in body['events']:
            if event['type'] == 'message' and event['message']['type'] == 'text':
                user_id = event['source']['userId']
                message_text = event['message']['text']
                reply_token = event['replyToken']
                
                if message_text in CITIES:
                    quick_reply = create_date_quick_reply(message_text)
                    send_line_reply(reply_token, f"{message_text}を選択しました。次に日付を選択してください。", quick_reply)
                else:
                    try:
                        city, date = message_text.split(':')
                        if city in CITIES:
                            date = parse_date(date)
                            if date == (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'):
                                weather_report = get_weather_report(city, date)
                                send_line_reply(reply_token, weather_report)
                            else:
                                table.put_item(Item={'user_id': user_id, 'date': date, 'city': city})
                                send_line_reply(reply_token, f"{city}の天気情報を{date}の1日前に通知します。")
                        else:
                            raise ValueError("Invalid city")
                    except ValueError:
                        quick_reply = create_city_quick_reply()
                        send_line_reply(reply_token, "天気を知りたい都市を選択してください。", quick_reply)
                    
        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }
    except Exception as e:
        print("Error:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps('Internal Server Error')
        }

def parse_date(date_input):
    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日']
    for fmt in date_formats:
        try:
            return datetime.strptime(date_input, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    raise ValueError("Invalid date format")

def get_weather_report(city, date):
    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHERMAP_API_KEY}&units=metric&lang=ja'
    response = requests.get(url)
    response.raise_for_status()
    forecast = response.json()
    for entry in forecast['list']:
        forecast_date = datetime.strptime(entry['dt_txt'], '%Y-%m-%d %H:%M:%S').date()
        if forecast_date == datetime.strptime(date, '%Y-%m-%d').date():
            description = entry['weather'][0]['description']
            temp = entry['main']['temp']
            return f"{city}の{date}の天気:\n天気: {description}\n温度: {temp}°C"
    return f"{city}の{date}の天気情報が見つかりませんでした。"

def send_line_reply(reply_token, message, quick_reply=None):
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer ' + LINE_ACCESS_TOKEN
    }
    payload = {
        'replyToken': reply_token,
        'messages': [{
            'type': 'text',
            'text': message
        }]
    }
    if quick_reply:
        payload['messages'][0]['quickReply'] = quick_reply

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    print("LINE API response:", response.json())
    response.raise_for_status()
    return response.json()

def create_city_quick_reply():
    quick_reply_items = []
    for city in CITIES:
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": city,
                "text": city
            }
        })
    return {
        "items": quick_reply_items
    }

def create_date_quick_reply(city):
    today = datetime.now().date()
    quick_reply_items = []
    for i in range(1, 11):
        target_date = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": target_date,
                "text": f"{city}:{target_date}"
            }
        })
    return {
        "items": quick_reply_items
    }
