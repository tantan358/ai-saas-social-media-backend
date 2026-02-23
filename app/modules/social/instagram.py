import requests
from typing import Dict, Any
from app.config import settings


class InstagramClient:
    """Instagram Graph API client for posting content"""
    
    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        self.account_id = account_id
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def post_content(self, content: str, image_url: str = None) -> Dict[str, Any]:
        """
        Post content to Instagram
        
        For MVP: Basic text post (Instagram requires media, so we'll create a simple post)
        In production: Support images, videos, carousels
        """
        # Instagram requires media for posts
        # For MVP, we'll create a basic media container
        
        if not image_url:
            # Use a placeholder or default image
            image_url = "https://via.placeholder.com/1080x1080"
        
        # Step 1: Create media container
        container_data = {
            "image_url": image_url,
            "caption": content,
            "access_token": self.access_token
        }
        
        container_response = requests.post(
            f"{self.base_url}/{self.account_id}/media",
            json=container_data
        )
        
        if container_response.status_code != 200:
            raise Exception(f"Failed to create Instagram media container: {container_response.text}")
        
        creation_id = container_response.json().get("id")
        
        # Step 2: Publish the media
        publish_data = {
            "creation_id": creation_id,
            "access_token": self.access_token
        }
        
        publish_response = requests.post(
            f"{self.base_url}/{self.account_id}/media_publish",
            json=publish_data
        )
        
        if publish_response.status_code != 200:
            raise Exception(f"Failed to publish Instagram post: {publish_response.text}")
        
        return {
            "post_id": publish_response.json().get("id"),
            "platform": "instagram",
            "status": "published"
        }
    
    def validate_token(self) -> bool:
        """Validate Instagram access token"""
        response = requests.get(
            f"{self.base_url}/me",
            params={"access_token": self.access_token}
        )
        
        return response.status_code == 200
