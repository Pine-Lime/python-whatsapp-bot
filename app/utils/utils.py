import requests
import datetime
import base64
from flask import current_app

def generate_s3_post_url(file_name, file_type, location):
    url = "https://pinenlime.com/_functions/uploadImage"
    headers = {'Content-Type': 'application/json'}
    data = {"file_name": file_name, "file_type": file_type, "bucketFolder": location, "bucket": "pinelime-orders"}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def uploadToS3(image_url, location="Test"):
    # Download the image from the URL
    headers = {
            "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
        }
    response = requests.get(image_url)
    if not response.ok:
        print(f"Error downloading image from {image_url}")
        return "Error downloading image"

    # Determine the file type from the image content type
    file_type = response.headers['Content-Type']

    # Convert the current time to a base64 string for the file name
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_name = base64.b64encode(current_time.encode()).decode()

    s3_links = generate_s3_post_url(file_name, file_type, location)

    # Upload the image to S3
    upload_response = requests.put(s3_links['url'], data=response.content, headers={"Content-Type": file_type})
    if upload_response.ok:
        return s3_links['objectURL']
    else:
        print(upload_response.text)
        return upload_response.text