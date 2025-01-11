import requests
import datetime
import base64
import json
from flask import current_app

def generate_s3_post_url(file_name, file_type, location):
    url = "https://pinenlime.com/_functions/uploadImage"
    headers = {'Content-Type': 'application/json'}
    data = {"file_name": file_name, "file_type": file_type, "bucketFolder": location, "bucket": "pinelime-orders"}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def uploadToS3(image_data, location="Test"):
    """
    Upload image to S3
    image_data can be either a URL string or bytes
    """
    try:
        if isinstance(image_data, str):
            # If image_data is a URL, download it
            headers = {
                "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
            }
            response = requests.get(image_data)
            if not response.ok:
                print(f"Error downloading image from {image_data}")
                return "Error downloading image"
            content = response.content
            file_type = response.headers['Content-Type']
        else:
            # If image_data is bytes, use it directly
            content = image_data
            file_type = 'image/jpeg'  # Default to JPEG if unknown

        # Generate filename using timestamp
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_name = base64.b64encode(current_time.encode()).decode()

        # Get S3 upload URL
        s3_links = generate_s3_post_url(file_name, file_type, location)

        # Upload to S3
        upload_response = requests.put(s3_links['url'], data=content, headers={"Content-Type": file_type})
        if upload_response.ok:
            return s3_links['objectURL']
        else:
            print(upload_response.text)
            return upload_response.text

    except Exception as e:
        print(f"Error in uploadToS3: {str(e)}")
        return str(e)