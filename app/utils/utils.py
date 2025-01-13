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
            # If image_data is a URL, download it with proper headers
            headers = {
                "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
                "User-Agent": "WhatsAppBot/1.0"
            }
            
            # First, get the actual media URL
            media_id = image_data.split('mid=')[1].split('&')[0]
            media_url = f"https://graph.facebook.com/v18.0/{media_id}"
            
            # Get the actual download URL
            media_response = requests.get(media_url, headers=headers)
            if not media_response.ok:
                print(f"Error getting media URL: {media_response.text}")
                return "Error getting media URL"
                
            download_url = media_response.json().get('url')
            if not download_url:
                print("No download URL found in media response")
                return "No download URL found"
                
            # Download the actual image
            response = requests.get(download_url, headers=headers)
            if not response.ok:
                print(f"Error downloading image: {response.text}")
                return "Error downloading image"
            content = response.content
            file_type = response.headers.get('Content-Type', 'image/jpeg')
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
            print(f"Error uploading to S3: {upload_response.text}")
            return upload_response.text

    except Exception as e:
        print(f"Error in uploadToS3: {str(e)}")
        return str(e)