import requests
import datetime
import base64
import json
from flask import current_app
import logging
from io import BytesIO
from PIL import Image

def generate_s3_post_url(file_name, file_type, location):
    url = "https://pinenlime.com/_functions/uploadImage"
    headers = {'Content-Type': 'application/json'}
    data = {"file_name": file_name, "file_type": file_type, "bucketFolder": location, "bucket": "pinelime-orders"}
    response = requests.post(url, json=data, headers=headers)
    return response.json()

def process_face_cutout(image_url):
    """Process image through cutout.pro API for face detection"""
    try:
        # Call the cutout.pro API
        cutout_response = requests.get(
            f"https://www.cutout.pro/api/v1/mattingByUrl",
            params={
                "url": image_url,
                "mattingType": "3",
                "crop": "true",
                "preview": "true",
                "faceAnalysis": "true"
            },
            headers={
                "APIKEY": "2d4e70bdccd74b3d97bda50ddd9ea7f8"
            }
        )
        
        if not cutout_response.ok:
            logging.error(f"Cutout API error: {cutout_response.text}")
            return None, None
            
        cutout_data = cutout_response.json()
        
        if not cutout_data.get("data"):
            logging.error("No data in cutout response")
            return None, None
            
        # Get face analysis data
        face_points = cutout_data["data"].get("faceAnalysis", {}).get("faces", [])
        
        # Convert base64 to image content
        image_base64 = cutout_data["data"].get("imageBase64")
        if not image_base64:
            logging.error("No image data in response")
            return None, face_points
            
        image_content = base64.b64decode(image_base64)
        
        # Upload processed image to S3
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"processed_{current_time}.png"
        
        s3_links = generate_s3_post_url(file_name, "image/png", "processed_images")
        
        # Upload to S3
        upload_response = requests.put(
            s3_links['url'], 
            data=image_content, 
            headers={"Content-Type": "image/png"}
        )
        
        if not upload_response.ok:
            logging.error(f"S3 upload error: {upload_response.text}")
            return None, face_points
            
        return s3_links['objectURL'], face_points
        
    except Exception as e:
        logging.error(f"Error in face cutout processing: {e}")
        return None, None

def uploadToS3(image_data, location="Test"):
    """
    Upload image to S3 and process face cutout
    image_data can be either a media ID, URL string, or bytes
    """
    try:
        if isinstance(image_data, str):
            headers = {
                "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
                "User-Agent": "WhatsAppBot/1.0"
            }
            
            # If it's a URL starting with http, use it directly
            if image_data.startswith('http'):
                media_id = image_data.split('mid=')[1].split('&')[0] if 'mid=' in image_data else None
            else:
                # Assume it's a media ID
                media_id = image_data
                
            if not media_id:
                print("No media ID found")
                return "No media ID found"
                
            # Get the media URL
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
        if not upload_response.ok:
            print(f"Error uploading to S3: {upload_response.text}")
            return upload_response.text
            
        original_url = s3_links['objectURL']
        
        # Process face cutout
        processed_url, face_points = process_face_cutout(original_url)
        
        return {
            "original_url": original_url,
            "processed_url": processed_url,
            "face_points": face_points
        }

    except Exception as e:
        print(f"Error in uploadToS3: {str(e)}")
        return str(e)