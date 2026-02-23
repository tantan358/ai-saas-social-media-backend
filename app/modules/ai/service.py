from typing import Dict, Any, List
from app.config import settings
import requests
import json


class AIService:
    """AI service for generating campaign plans and posts"""
    
    @staticmethod
    def generate_campaign_plan(
        campaign_name: str,
        description: str = None,
        language: str = "es"
    ) -> Dict[str, Any]:
        """
        Generate AI campaign plan
        
        For MVP: Returns a mock plan structure
        In production: Integrate with OpenAI, Anthropic, etc.
        """
        # Mock AI plan for MVP
        plan = {
            "theme": campaign_name,
            "description": description or "",
            "language": language,
            "posts_count": 5,
            "posting_schedule": "daily",
            "content_themes": [
                f"Introduction to {campaign_name}",
                f"Benefits of {campaign_name}",
                f"Success stories related to {campaign_name}",
                f"Tips and best practices for {campaign_name}",
                f"Call to action for {campaign_name}"
            ],
            "target_audience": "General audience",
            "tone": "Professional and engaging"
        }
        
        # In production, make API call:
        # if settings.AI_API_KEY:
        #     response = requests.post(
        #         f"{settings.AI_API_URL}/chat/completions",
        #         headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
        #         json={
        #             "model": "gpt-4",
        #             "messages": [
        #                 {"role": "system", "content": f"Generate a social media campaign plan in {language}"},
        #                 {"role": "user", "content": f"Campaign: {campaign_name}\nDescription: {description}"}
        #             ]
        #         }
        #     )
        #     plan = response.json()
        
        return plan
    
    @staticmethod
    def generate_posts(
        campaign_plan: Dict[str, Any],
        language: str = "es"
    ) -> List[Dict[str, Any]]:
        """
        Generate posts from campaign plan
        
        For MVP: Returns mock posts
        In production: Use AI to generate actual content
        """
        posts = []
        content_themes = campaign_plan.get("content_themes", [])
        posts_count = campaign_plan.get("posts_count", 5)
        
        # Mock posts for MVP
        for i, theme in enumerate(content_themes[:posts_count]):
            platform = "linkedin" if i % 2 == 0 else "instagram"
            
            if language == "es":
                content = f"🎯 {theme}\n\nEste es un post de ejemplo generado para la campaña. Contenido relevante y atractivo que se adapta al tema: {theme}.\n\n#MarketingDigital #SocialMedia"
            else:
                content = f"🎯 {theme}\n\nThis is an example post generated for the campaign. Relevant and engaging content that adapts to the theme: {theme}.\n\n#DigitalMarketing #SocialMedia"
            
            posts.append({
                "content": content,
                "platform": platform,
                "metadata": {
                    "theme": theme,
                    "order": i + 1
                }
            })
        
        # In production, make API call to generate actual content:
        # if settings.AI_API_KEY:
        #     response = requests.post(
        #         f"{settings.AI_API_URL}/chat/completions",
        #         headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
        #         json={
        #             "model": "gpt-4",
        #             "messages": [
        #                 {"role": "system", "content": f"Generate social media posts in {language} based on this plan"},
        #                 {"role": "user", "content": json.dumps(campaign_plan)}
        #             ]
        #         }
        #     )
        #     # Process response and create posts
        
        return posts
