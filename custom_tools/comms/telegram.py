import os

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot"


def send_telegram_message(recipient: str, msg: str) -> None:
    """
    Send a Telegram message to a recipient
    Args:
    - recipient (str): Target chat or username of the target channel (in the format @channelusername)
    - msg (str): Text of the message to be sent
    """
    TELEGRAM_API_TOKEN = os.environ.get("TELEGRAM_API_TOKEN")
    api_url = f"{TELEGRAM_API_URL}{TELEGRAM_API_TOKEN}"

    if recipient.startswith("@"):
        recipient = recipient[1:]

    updates_request = requests.get(f"{api_url}/getUpdates")
    updates = updates_request.json().get("result")
    for message in updates:
        user = message["message"]["from"]
        if user["username"] == recipient:
            chat_id = user["id"]

    payload = {
        "chat_id": chat_id,
        "text": msg,
    }
    requests.post(f"{api_url}/sendMessage", data=payload)
