import json
import requests
import datetime
import boto3
import os

ssm = boto3.client('ssm')

def get_ssm_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

OPENWEATHERMAP_API_KEY = get_ssm_parameter(os.environ['OPENWEATHERMAP_API_KEY_SSM'])
LINE_ACCESS_TOKEN = get_ssm_parameter(os.environ['LINE_ACCESS_TOKEN_SSM'])
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHERMAP_API_KEY}&units=metric&lang=ja"
    response = requests.get(url)
    return response.json()

def send_line_message(user_id, message):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    payload = {
        'to': user_id,
        'messages': [{
            'type': 'text',
            'text': message
        }]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response.json()

def lambda_handler(event, context):
    today = datetime.date.today()
    target_date = today + datetime.timedelta(days=1)
    target_date_str = target_date.strftime('%Y-%m-%d')

    response = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('date').eq(target_date_str)
    )

    for item in response['Items']:
        city = item['city']
        user_id = item['user_id']
        weather = get_weather(city)
        message = f"{target_date_str}の{city}の天気は: {weather['weather'][0]['description']}, 気温: {weather['main']['temp']}°C"
        send_line_message(user_id, message)

    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }
