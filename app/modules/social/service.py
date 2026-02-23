from sqlalchemy.orm import Session
from app.modules.social.models import SocialAccount, PlatformType
from app.modules.social.schemas import SocialAccountCreate
from app.modules.social.linkedin import LinkedInClient
from app.modules.social.instagram import InstagramClient
from app.modules.campaigns.models import Post, PostStatus
from fastapi import HTTPException, status
from typing import List


class SocialService:
    @staticmethod
    def create_account(
        db: Session,
        account_data: SocialAccountCreate,
        tenant_id: int
    ) -> SocialAccount:
        """Create a new social media account connection"""
        account = SocialAccount(
            tenant_id=tenant_id,
            platform=account_data.platform,
            account_name=account_data.account_name,
            account_id=account_data.account_id,
            access_token=account_data.access_token,
            refresh_token=account_data.refresh_token,
            metadata=account_data.metadata
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account
    
    @staticmethod
    def get_accounts(
        db: Session,
        tenant_id: int,
        platform: PlatformType = None
    ) -> List[SocialAccount]:
        """Get social accounts for tenant"""
        query = db.query(SocialAccount).filter(SocialAccount.tenant_id == tenant_id)
        if platform:
            query = query.filter(SocialAccount.platform == platform)
        return query.all()
    
    @staticmethod
    def publish_post(
        db: Session,
        post_id: int,
        social_account_id: int,
        tenant_id: int
    ) -> Post:
        """Publish a post to social media"""
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.tenant_id == tenant_id
        ).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        
        if post.status != PostStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post must be approved before publishing"
            )
        
        account = db.query(SocialAccount).filter(
            SocialAccount.id == social_account_id,
            SocialAccount.tenant_id == tenant_id
        ).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Social account not found"
            )
        
        # Publish based on platform
        try:
            if account.platform == PlatformType.LINKEDIN:
                client = LinkedInClient(account.access_token)
                result = client.post_content(post.content, account.account_id)
            elif account.platform == PlatformType.INSTAGRAM:
                client = InstagramClient(account.access_token, account.account_id)
                image_url = post.metadata.get("image_url") if post.metadata else None
                result = client.post_content(post.content, image_url)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported platform: {account.platform}"
                )
            
            # Update post status
            post.status = PostStatus.PUBLISHED
            post.published_post_id = result.get("post_id")
            from datetime import datetime
            post.published_at = datetime.utcnow()
            
            db.commit()
            db.refresh(post)
            return post
            
        except Exception as e:
            post.status = PostStatus.FAILED
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to publish post: {str(e)}"
            )
