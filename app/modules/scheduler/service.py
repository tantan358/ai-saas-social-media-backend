from sqlalchemy.orm import Session
from app.modules.scheduler.models import ScheduledPost, ScheduledPostStatus
from app.modules.scheduler.schemas import ScheduledPostCreate
from app.modules.campaigns.models import Post, PostStatus
from app.modules.social.service import SocialService
from fastapi import HTTPException, status
from typing import List
from datetime import datetime


class SchedulerService:
    @staticmethod
    def schedule_post(
        db: Session,
        schedule_data: ScheduledPostCreate,
        tenant_id: int
    ) -> ScheduledPost:
        """Schedule a post for future publishing"""
        # Verify post exists and is approved
        post = db.query(Post).filter(
            Post.id == schedule_data.post_id,
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
                detail="Post must be approved before scheduling"
            )
        
        # Verify scheduled time is in future
        if schedule_data.scheduled_at <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be in the future"
            )
        
        scheduled_post = ScheduledPost(
            tenant_id=tenant_id,
            post_id=schedule_data.post_id,
            social_account_id=schedule_data.social_account_id,
            scheduled_at=schedule_data.scheduled_at,
            status=ScheduledPostStatus.SCHEDULED
        )
        
        db.add(scheduled_post)
        post.status = PostStatus.SCHEDULED
        db.commit()
        db.refresh(scheduled_post)
        return scheduled_post
    
    @staticmethod
    def get_scheduled_posts(
        db: Session,
        tenant_id: int,
        status_filter: ScheduledPostStatus = None
    ) -> List[ScheduledPost]:
        """Get scheduled posts for tenant"""
        query = db.query(ScheduledPost).filter(
            ScheduledPost.tenant_id == tenant_id
        )
        if status_filter:
            query = query.filter(ScheduledPost.status == status_filter)
        return query.order_by(ScheduledPost.scheduled_at).all()
    
    @staticmethod
    def pause_scheduled_post(
        db: Session,
        scheduled_post_id: int,
        tenant_id: int
    ) -> ScheduledPost:
        """Pause a scheduled post"""
        scheduled_post = db.query(ScheduledPost).filter(
            ScheduledPost.id == scheduled_post_id,
            ScheduledPost.tenant_id == tenant_id
        ).first()
        
        if not scheduled_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled post not found"
            )
        
        if scheduled_post.status not in [ScheduledPostStatus.SCHEDULED, ScheduledPostStatus.PENDING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only pause scheduled or pending posts"
            )
        
        scheduled_post.status = ScheduledPostStatus.PAUSED
        db.commit()
        db.refresh(scheduled_post)
        return scheduled_post
    
    @staticmethod
    def cancel_scheduled_post(
        db: Session,
        scheduled_post_id: int,
        tenant_id: int
    ) -> ScheduledPost:
        """Cancel a scheduled post"""
        scheduled_post = db.query(ScheduledPost).filter(
            ScheduledPost.id == scheduled_post_id,
            ScheduledPost.tenant_id == tenant_id
        ).first()
        
        if not scheduled_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled post not found"
            )
        
        if scheduled_post.status == ScheduledPostStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel already published post"
            )
        
        scheduled_post.status = ScheduledPostStatus.CANCELLED
        db.commit()
        db.refresh(scheduled_post)
        return scheduled_post
    
    @staticmethod
    def process_due_posts(db: Session) -> List[ScheduledPost]:
        """Process posts that are due for publishing (called by worker)"""
        now = datetime.utcnow()
        
        due_posts = db.query(ScheduledPost).filter(
            ScheduledPost.status == ScheduledPostStatus.SCHEDULED,
            ScheduledPost.scheduled_at <= now
        ).all()
        
        published = []
        for scheduled_post in due_posts:
            try:
                scheduled_post.status = ScheduledPostStatus.PUBLISHING
                db.commit()
                
                # Publish the post
                SocialService.publish_post(
                    db,
                    scheduled_post.post_id,
                    scheduled_post.social_account_id,
                    scheduled_post.tenant_id
                )
                
                scheduled_post.status = ScheduledPostStatus.PUBLISHED
                scheduled_post.published_at = datetime.utcnow()
                db.commit()
                published.append(scheduled_post)
                
            except Exception as e:
                scheduled_post.status = ScheduledPostStatus.FAILED
                scheduled_post.error_message = str(e)
                db.commit()
        
        return published
