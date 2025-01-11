import logging
from flask import current_app, jsonify
import json
import requests
from .utils import uploadToS3

from app.services.openai_service import generate_response
import re


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


# def generate_response(response):
#     # Return text in uppercase
#     return response.upper()


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def process_whatsapp_message(body):
    logging.info(body)
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]

    # Check if the message contains an image
    if message.get("image"):
        image_id = message["image"]["id"]
        image_url = get_image_url(image_id)
        uploadToS3(image_url)
        logging.info(f"Received image: {image_url}")
        # You can now process the image URL, such as downloading or storing it
        response_text = "Image received, thank you!"
    else:
        # Process regular text message
        message_body = message["text"]["body"]
        response_text = generate_response(message_body, wa_id, name)

    # Prepare response message
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response_text)
    send_message(data)


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )


def get_image_url(media_id):
    headers = {
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{media_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        image_url = response.json().get("url")
        return image_url
    except requests.RequestException as e:
        logging.error(f"Failed to get image URL: {e}")
        return None


def download_image(image_url):
    try:
        headers = {
            "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
        }
        response = requests.get(image_url, stream=True, headers=headers)
        if response.status_code == 200:
            # Save the image locally or process as needed
            with open("received_image.jpg", "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logging.info("Image downloaded successfully.")
        else:
            logging.error(
                f"Failed to download image, status code: {response.status_code}"
            )
    except requests.RequestException as e:
        logging.error(f"Error downloading image: {e}")