import requests
from typing import Dict, Any, Optional
from app.config import settings


class LinkedInClient:
    """LinkedIn API client for posting content"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.linkedin.com/v2"
    
    def post_content(self, content: str, account_id: str = None) -> Dict[str, Any]:
        """
        Post content to LinkedIn
        
        For MVP: Basic text post
        In production: Support images, videos, etc.
        """
        # LinkedIn API requires URN format for person or organization
        # For MVP, we'll use a simplified approach
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Get user profile to get person URN
        profile_response = requests.get(
            f"{self.base_url}/me",
            headers=headers
        )
        
        if profile_response.status_code != 200:
            raise Exception(f"Failed to get LinkedIn profile: {profile_response.text}")
        
        person_urn = profile_response.json().get("id")
        
        # Create share
        share_data = {
            "author": f"urn:li:person:{person_urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = requests.post(
            f"{self.base_url}/ugcPosts",
            headers=headers,
            json=share_data
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to post to LinkedIn: {response.text}")
        
        return {
            "post_id": response.json().get("id"),
            "platform": "linkedin",
            "status": "published"
        }
    
    def validate_token(self) -> bool:
        """Validate LinkedIn access token"""
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        response = requests.get(
            f"{self.base_url}/me",
            headers=headers
        )
        
        return response.status_code == 200
