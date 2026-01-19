"""
Social Media Integration API Routes
Handles Instagram, Twitter, Facebook, LinkedIn integrations for marketing automation
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/social-media", tags=["Social Media"])

# ==================== Models ====================

class PostContent(BaseModel):
    caption: str
    hashtags: List[str] = []
    location: Optional[str] = None
    scheduled_time: Optional[str] = None  # ISO format

class InstagramPostRequest(BaseModel):
    media_url: Optional[str] = None  # For URL-based media
    caption: str
    hashtags: List[str] = []
    location: Optional[str] = None
    scheduled_time: Optional[str] = None

class ScheduleRequest(BaseModel):
    platform: str  # instagram, twitter, facebook, linkedin
    content: PostContent
    scheduled_time: str  # ISO format

class AnalyticsRequest(BaseModel):
    platform: str
    post_id: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None

# ==================== In-Memory Storage (replace with DB) ====================

scheduled_posts = []
connected_accounts = {}
post_analytics = {}

# ==================== Authentication Endpoints ====================

@router.post("/{platform}/connect")
async def connect_platform(
    platform: str,
    credentials: Dict[str, str] = Body(...)
) -> Dict[str, Any]:
    """
    Connect a social media platform account
    
    Supported platforms: instagram, twitter, facebook, linkedin
    
    Required credentials vary by platform:
    - Instagram: access_token, user_id
    - Twitter: api_key, api_secret, access_token, access_token_secret
    - Facebook: access_token, page_id
    - LinkedIn: access_token, person_id
    """
    supported = ["instagram", "twitter", "facebook", "linkedin", "tiktok"]
    if platform not in supported:
        raise HTTPException(status_code=400, detail=f"Platform not supported. Use: {supported}")
    
    try:
        # Validate credentials (placeholder - real impl would verify with platform API)
        required_fields = {
            "instagram": ["access_token", "user_id"],
            "twitter": ["api_key", "access_token"],
            "facebook": ["access_token", "page_id"],
            "linkedin": ["access_token"],
            "tiktok": ["access_token"]
        }
        
        for field in required_fields.get(platform, []):
            if field not in credentials:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Store connection (in real impl, encrypt and store securely)
        connected_accounts[platform] = {
            "connected": True,
            "connected_at": datetime.now().isoformat(),
            "credentials_masked": {k: "***" for k in credentials.keys()},
            "platform": platform
        }
        
        logger.info(f"Connected {platform} account successfully")
        
        return {
            "success": True,
            "platform": platform,
            "status": "connected",
            "message": f"{platform.title()} account connected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect {platform}: {e}")
        return {"success": False, "error": str(e)}

@router.get("/{platform}/status")
async def get_platform_status(platform: str) -> Dict[str, Any]:
    """Get connection status for a platform"""
    if platform in connected_accounts:
        return {
            "platform": platform,
            "connected": True,
            **connected_accounts[platform]
        }
    return {
        "platform": platform,
        "connected": False,
        "message": "Not connected. Use /connect endpoint."
    }

@router.delete("/{platform}/disconnect")
async def disconnect_platform(platform: str) -> Dict[str, Any]:
    """Disconnect a social media platform"""
    if platform in connected_accounts:
        del connected_accounts[platform]
        return {
            "success": True,
            "platform": platform,
            "message": f"{platform.title()} disconnected"
        }
    return {
        "success": False,
        "message": "Platform not connected"
    }

# ==================== Instagram Endpoints ====================

@router.post("/instagram/post")
async def post_to_instagram(request: InstagramPostRequest) -> Dict[str, Any]:
    """
    Post content to Instagram
    
    Supports:
    - Image posts
    - Video posts (reels)
    - Carousel posts
    
    For videos, upload first using /instagram/upload-media
    """
    if "instagram" not in connected_accounts:
        raise HTTPException(
            status_code=401,
            detail="Instagram not connected. Use /instagram/connect first."
        )
    
    try:
        # Build caption with hashtags
        full_caption = request.caption
        if request.hashtags:
            hashtag_str = " ".join([f"#{tag.lstrip('#')}" for tag in request.hashtags])
            full_caption += f"\n\n{hashtag_str}"
        
        # Simulate posting (real impl would call Instagram Graph API)
        post_id = f"insta_post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        post_data = {
            "id": post_id,
            "platform": "instagram",
            "caption": full_caption,
            "media_url": request.media_url,
            "location": request.location,
            "posted_at": datetime.now().isoformat(),
            "permalink": f"https://www.instagram.com/p/{post_id}",
            "status": "published"
        }
        
        # Store for analytics
        post_analytics[post_id] = {
            **post_data,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "reach": 0,
            "engagement_rate": 0.0
        }
        
        logger.info(f"Posted to Instagram: {post_id}")
        
        return {
            "success": True,
            "post_id": post_id,
            "permalink": post_data["permalink"],
            "message": "Posted successfully to Instagram"
        }
        
    except Exception as e:
        logger.error(f"Instagram post failed: {e}")
        return {"success": False, "error": str(e)}

@router.post("/instagram/upload-media")
async def upload_instagram_media(
    file: UploadFile = File(...),
    media_type: str = "image"  # image, video, reel
) -> Dict[str, Any]:
    """
    Upload media for Instagram posting
    
    Supports:
    - Images: JPG, PNG (max 8MB)
    - Videos: MP4 (max 100MB for reels, 60s max)
    
    Returns a media_url to use with /instagram/post
    """
    try:
        # Validate file
        allowed_types = {
            "image": [".jpg", ".jpeg", ".png"],
            "video": [".mp4", ".mov"],
            "reel": [".mp4"]
        }
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_types.get(media_type, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for {media_type}. Allowed: {allowed_types[media_type]}"
            )
        
        # Save file (in real impl, upload to cloud storage)
        upload_dir = "uploads/instagram"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = f"{upload_dir}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        media_url = f"/media/{file_path}"
        
        return {
            "success": True,
            "media_url": media_url,
            "media_type": media_type,
            "filename": file.filename,
            "size_bytes": len(content),
            "message": "Media uploaded successfully. Use media_url in /instagram/post"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media upload failed: {e}")
        return {"success": False, "error": str(e)}

@router.get("/instagram/insights/{post_id}")
async def get_instagram_insights(post_id: str) -> Dict[str, Any]:
    """Get analytics for a specific Instagram post"""
    if post_id in post_analytics:
        return {
            "success": True,
            **post_analytics[post_id]
        }
    return {
        "success": False,
        "message": "Post not found"
    }

# ==================== Scheduling Endpoints ====================

@router.post("/schedule")
async def schedule_post(request: ScheduleRequest) -> Dict[str, Any]:
    """
    Schedule a post for future publishing
    
    Works with all supported platforms:
    - instagram
    - twitter
    - facebook
    - linkedin
    """
    try:
        schedule_id = f"sched_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        scheduled_post = {
            "id": schedule_id,
            "platform": request.platform,
            "content": request.content.dict(),
            "scheduled_time": request.scheduled_time,
            "created_at": datetime.now().isoformat(),
            "status": "scheduled"
        }
        
        scheduled_posts.append(scheduled_post)
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "scheduled_time": request.scheduled_time,
            "platform": request.platform,
            "message": f"Post scheduled for {request.scheduled_time}"
        }
        
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        return {"success": False, "error": str(e)}

@router.get("/schedule")
async def get_scheduled_posts(
    platform: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """Get all scheduled posts, optionally filtered by platform or status"""
    filtered = scheduled_posts
    
    if platform:
        filtered = [p for p in filtered if p["platform"] == platform]
    if status:
        filtered = [p for p in filtered if p["status"] == status]
    
    return {
        "success": True,
        "total": len(filtered),
        "scheduled_posts": filtered
    }

@router.delete("/schedule/{schedule_id}")
async def cancel_scheduled_post(schedule_id: str) -> Dict[str, Any]:
    """Cancel a scheduled post"""
    global scheduled_posts
    
    for i, post in enumerate(scheduled_posts):
        if post["id"] == schedule_id:
            scheduled_posts[i]["status"] = "cancelled"
            return {
                "success": True,
                "message": f"Scheduled post {schedule_id} cancelled"
            }
    
    return {
        "success": False,
        "message": "Scheduled post not found"
    }

# ==================== Analytics Endpoints ====================

@router.get("/analytics/{platform}")
async def get_platform_analytics(
    platform: str,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get analytics overview for a platform
    
    Returns:
    - Total posts
    - Total engagement
    - Average engagement rate
    - Top performing posts
    """
    platform_posts = [
        p for p in post_analytics.values()
        if p.get("platform") == platform
    ]
    
    total_likes = sum(p.get("likes", 0) for p in platform_posts)
    total_comments = sum(p.get("comments", 0) for p in platform_posts)
    total_reach = sum(p.get("reach", 0) for p in platform_posts)
    
    return {
        "success": True,
        "platform": platform,
        "period_days": days,
        "stats": {
            "total_posts": len(platform_posts),
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_reach": total_reach,
            "avg_engagement_rate": (total_likes + total_comments) / max(total_reach, 1) * 100
        },
        "top_posts": sorted(
            platform_posts,
            key=lambda x: x.get("likes", 0) + x.get("comments", 0),
            reverse=True
        )[:5]
    }

# ==================== Content Creation Endpoints ====================

@router.post("/generate-caption")
async def generate_caption(
    topic: str = Body(...),
    style: str = Body("professional"),  # professional, casual, funny, inspirational
    platform: str = Body("instagram"),
    include_hashtags: bool = Body(True)
) -> Dict[str, Any]:
    """
    Generate a social media caption using AI
    
    Styles: professional, casual, funny, inspirational
    """
    try:
        # In real impl, call LLM to generate caption
        # For now, return template
        
        sample_captions = {
            "professional": f"Excited to share insights about {topic}! 🚀 Stay tuned for more updates.",
            "casual": f"Just had to share this about {topic}! What do you think? 👀",
            "funny": f"When {topic} hits different 😂 Drop a comment if you relate!",
            "inspirational": f"Remember: every step towards {topic} is a step towards greatness ✨"
        }
        
        caption = sample_captions.get(style, sample_captions["professional"])
        
        hashtags = []
        if include_hashtags:
            hashtags = [
                f"#{topic.replace(' ', '').lower()}",
                "#marketing",
                "#socialmedia",
                "#growth",
                "#business"
            ]
        
        return {
            "success": True,
            "caption": caption,
            "hashtags": hashtags,
            "style": style,
            "platform": platform,
            "character_count": len(caption)
        }
        
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        return {"success": False, "error": str(e)}

# ==================== Multi-Platform Endpoints ====================

@router.post("/post-all")
async def post_to_all_platforms(
    content: PostContent,
    platforms: List[str] = Body(["instagram", "twitter"])
) -> Dict[str, Any]:
    """
    Post same content to multiple platforms at once
    """
    results = {}
    
    for platform in platforms:
        if platform not in connected_accounts:
            results[platform] = {
                "success": False,
                "error": f"{platform} not connected"
            }
            continue
        
        # Simulate posting to each platform
        post_id = f"{platform}_post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        results[platform] = {
            "success": True,
            "post_id": post_id,
            "message": f"Posted to {platform}"
        }
    
    return {
        "success": all(r.get("success", False) for r in results.values()),
        "results": results,
        "posted_count": sum(1 for r in results.values() if r.get("success", False)),
        "total": len(platforms)
    }

@router.get("/connected")
async def get_all_connected_platforms() -> Dict[str, Any]:
    """Get list of all connected social media platforms"""
    return {
        "success": True,
        "connected_platforms": list(connected_accounts.keys()),
        "total": len(connected_accounts),
        "accounts": connected_accounts
    }
