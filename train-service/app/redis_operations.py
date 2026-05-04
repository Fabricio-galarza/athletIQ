"""
Redis operations for caching user profiles, workouts, and feedback.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.core.cache import cache

logger = logging.getLogger(__name__)


class RedisOperations:
    """
    Handles all Redis operations for:
    - User profiles
    - Workout plans
    - Daily workouts
    - Feedback history
    """
    
    # Key prefixes
    USER_PREFIX = "user:"
    WORKOUT_PREFIX = "workout:"
    WORKOUT_DAY_PREFIX = "workout:day:"
    FEEDBACK_PREFIX = "feedback:"
    
    def __init__(self):
        self.cache = cache
    
    # ============================================
    # User Profile Operations
    # ============================================
    
    async def save_user_profile(self, user_id: str, profile: Dict[str, Any], ttl: int = 86400) -> bool:
        """
        Save user profile to Redis.
        
        Args:
            user_id: User identifier
            profile: User profile data
            ttl: Time to live in seconds (default 24 hours)
        """
        key = f"{self.USER_PREFIX}{user_id}"
        return await self.cache.set(key, profile, ttl)
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from Redis."""
        key = f"{self.USER_PREFIX}{user_id}"
        return await self.cache.get(key)
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of user profile."""
        profile = await self.get_user_profile(user_id)
        if profile:
            profile.update(updates)
            return await self.save_user_profile(user_id, profile)
        return False
    
    async def delete_user_profile(self, user_id: str) -> bool:
        """Delete user profile from Redis."""
        key = f"{self.USER_PREFIX}{user_id}"
        return await self.cache.delete(key)
    
    # ============================================
    # Workout Plan Operations
    # ============================================
    
    async def save_workout_plan(self, plan_id: str, plan: Dict[str, Any], ttl: int = 604800) -> bool:
        """
        Save complete workout plan to Redis.
        
        Args:
            plan_id: Plan identifier
            plan: Complete plan data
            ttl: Time to live in seconds (default 7 days)
        """
        key = f"{self.WORKOUT_PREFIX}{plan_id}"
        return await self.cache.set(key, plan, ttl)
    
    async def get_workout_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get workout plan from Redis."""
        key = f"{self.WORKOUT_PREFIX}{plan_id}"
        return await self.cache.get(key)
    
    async def get_active_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's currently active workout plan."""
        profile = await self.get_user_profile(user_id)
        if profile and profile.get("active_plan_id"):
            return await self.get_workout_plan(profile["active_plan_id"])
        return None
    
    async def set_active_plan(self, user_id: str, plan_id: str) -> bool:
        """Set user's active plan."""
        return await self.update_user_profile(user_id, {"active_plan_id": plan_id})
    
    # ============================================
    # Daily Workout Operations
    # ============================================
    
    async def save_daily_workout(
        self,
        plan_id: str,
        day: int,
        workout: Dict[str, Any],
        ttl: int = 604800
    ) -> bool:
        """
        Save specific day's workout.
        
        Args:
            plan_id: Plan identifier
            day: Day number (1-7)
            workout: Daily workout data
            ttl: Time to live in seconds
        """
        key = f"{self.WORKOUT_DAY_PREFIX}{plan_id}:day_{day}"
        return await self.cache.set(key, workout, ttl)
    
    async def get_daily_workout(self, plan_id: str, day: int) -> Optional[Dict[str, Any]]:
        """Get specific day's workout."""
        key = f"{self.WORKOUT_DAY_PREFIX}{plan_id}:day_{day}"
        return await self.cache.get(key)
    
    async def get_today_workout(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get today's workout for user.
        Calculates current day based on plan start date.
        """
        profile = await self.get_user_profile(user_id)
        if not profile or not profile.get("active_plan_id"):
            return None
        
        plan_id = profile["active_plan_id"]
        plan = await self.get_workout_plan(plan_id)
        
        if not plan:
            return None
        
        # Calculate current day based on plan start
        start_date = datetime.fromisoformat(plan.get("created_at"))
        days_since_start = (datetime.now() - start_date).days
        current_day = (days_since_start % plan.get("days_per_week", 7)) + 1
        
        return await self.get_daily_workout(plan_id, current_day)
    
    # ============================================
    # Feedback Operations
    # ============================================
    
    async def save_feedback(
        self,
        user_id: str,
        plan_id: str,
        day: int,
        feedback: Dict[str, Any],
        ttl: int = 2592000  # 30 days
    ) -> bool:
        """
        Save user feedback for a workout.
        
        Args:
            user_id: User identifier
            plan_id: Plan identifier
            day: Day number
            feedback: Feedback data
            ttl: Time to live in seconds
        """
        feedback_with_metadata = {
            **feedback,
            "user_id": user_id,
            "plan_id": plan_id,
            "day": day,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Store in list for history
        list_key = f"{self.FEEDBACK_PREFIX}{user_id}:{plan_id}"
        await self.cache._client.rpush(list_key, json.dumps(feedback_with_metadata))
        await self.cache._client.expire(list_key, ttl)
        
        # Also store latest feedback separately
        latest_key = f"{self.FEEDBACK_PREFIX}{user_id}:latest"
        return await self.cache.set(latest_key, feedback_with_metadata, ttl)
    
    async def get_feedback_history(
        self,
        user_id: str,
        plan_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get feedback history for user."""
        if plan_id:
            list_key = f"{self.FEEDBACK_PREFIX}{user_id}:{plan_id}"
        else:
            # Get all feedback keys for user
            pattern = f"{self.FEEDBACK_PREFIX}{user_id}:*"
            keys = await self.cache._client.keys(pattern)
            if not keys:
                return []
            # Use the most recent key
            list_key = keys[-1] if keys else None
        
        if not list_key:
            return []
        
        # Get last 'limit' feedback entries
        start = -limit
        items = await self.cache._client.lrange(list_key, start, -1)
        
        results = []
        for item in items:
            try:
                results.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        
        return list(reversed(results))
    
    async def get_latest_feedback(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get most recent feedback from user."""
        latest_key = f"{self.FEEDBACK_PREFIX}{user_id}:latest"
        return await self.cache.get(latest_key)
    
    async def calculate_completion_rate(
        self,
        user_id: str,
        plan_id: str,
        days: int = 7
    ) -> float:
        """
        Calculate completion rate for recent workouts.
        """
        feedbacks = await self.get_feedback_history(user_id, plan_id, days)
        
        if not feedbacks:
            return 0.0
        
        completed = sum(1 for f in feedbacks if f.get("completed", False))
        return (completed / len(feedbacks)) * 100
    
    async def get_average_difficulty(self, user_id: str, plan_id: str, days: int = 7) -> float:
        """
        Calculate average difficulty rating from recent feedback.
        """
        feedbacks = await self.get_feedback_history(user_id, plan_id, days)
        
        if not feedbacks:
            return 5.0  # Default neutral
        
        difficulties = [f.get("difficulty", 5) for f in feedbacks if f.get("difficulty")]
        
        if not difficulties:
            return 5.0
        
        return sum(difficulties) / len(difficulties)
    
    # ============================================
    # Utility Operations
    # ============================================
    
    async def clear_user_data(self, user_id: str) -> int:
        """
        Clear all data related to a user.
        Returns number of keys deleted.
        """
        patterns = [
            f"{self.USER_PREFIX}{user_id}",
            f"{self.WORKOUT_PREFIX}*",
            f"{self.FEEDBACK_PREFIX}{user_id}:*",
        ]
        
        deleted = 0
        for pattern in patterns:
            keys = await self.cache._client.keys(pattern)
            if keys:
                deleted += await self.cache._client.delete(*keys)
        
        return deleted
    
    async def health_check(self) -> bool:
        """Check if Redis is accessible."""
        try:
            await self.cache._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Singleton instance
redis_ops = RedisOperations()