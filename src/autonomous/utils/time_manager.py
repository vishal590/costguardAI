"""
Time Management Utility for Demo Mode

Provides centralized time compression for demo mode across all autonomous
Lambda functions. Compresses 7-day analysis windows to 5-minute windows
using a 2,016x time compression factor.

Usage:
    from autonomous.utils.time_manager import TimeManager
    
    # Get compressed analysis window
    window = TimeManager.get_analysis_window(days=7)  # 5 min in demo mode
    
    # Get compressed polling interval
    interval = TimeManager.get_polling_interval(seconds=60)  # 10s in demo mode
    
    # Get compressed daily task interval
    daily_interval = TimeManager.get_daily_task_interval()  # 2 min in demo mode
"""

import os
from datetime import timedelta
from typing import Optional

# Demo mode flag
DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'


class TimeManager:
    """
    Manages time compression for demo mode.
    
    Compression factors:
    - 7 days → 5 minutes (2,016x compression)
    - 60 seconds → 10 seconds (6x compression)
    - 24 hours → 2 minutes (720x compression)
    """
    
    # Compression factors
    ANALYSIS_COMPRESSION = 2016  # 7 days (10,080 min) → 5 min
    POLLING_COMPRESSION = 6      # 60s → 10s
    DAILY_COMPRESSION = 720      # 24 hours (1,440 min) → 2 min
    
    @classmethod
    def is_demo_mode(cls) -> bool:
        """Check if demo mode is enabled."""
        return DEMO_MODE
    
    @classmethod
    def get_analysis_window(cls, days: int) -> timedelta:
        """
        Get analysis window duration with demo mode compression.
        
        Args:
            days: Number of days for analysis window
            
        Returns:
            timedelta: Compressed window in demo mode, normal window otherwise
            
        Examples:
            >>> TimeManager.get_analysis_window(7)  # Demo mode
            timedelta(minutes=5)
            >>> TimeManager.get_analysis_window(7)  # Normal mode
            timedelta(days=7)
        """
        if DEMO_MODE:
            # Compress time window for demo
            minutes = (days * 24 * 60) / cls.ANALYSIS_COMPRESSION
            return timedelta(minutes=minutes)
        return timedelta(days=days)
    
    @classmethod
    def get_polling_interval(cls, seconds: int) -> int:
        """
        Get polling interval with demo mode compression.
        
        Args:
            seconds: Normal polling interval in seconds
            
        Returns:
            int: Compressed interval in demo mode, normal interval otherwise
            
        Examples:
            >>> TimeManager.get_polling_interval(60)  # Demo mode
            10
            >>> TimeManager.get_polling_interval(60)  # Normal mode
            60
        """
        if DEMO_MODE:
            # Compress polling interval (60s → 10s)
            return max(1, seconds // cls.POLLING_COMPRESSION)
        return seconds
    
    @classmethod
    def get_daily_task_interval(cls) -> timedelta:
        """
        Get daily task interval with demo mode compression.
        
        Returns:
            timedelta: 2 minutes in demo mode, 24 hours otherwise
            
        Examples:
            >>> TimeManager.get_daily_task_interval()  # Demo mode
            timedelta(minutes=2)
            >>> TimeManager.get_daily_task_interval()  # Normal mode
            timedelta(days=1)
        """
        if DEMO_MODE:
            # Compress daily tasks (24 hours → 2 minutes)
            minutes = (24 * 60) / cls.DAILY_COMPRESSION
            return timedelta(minutes=minutes)
        return timedelta(days=1)
    
    @classmethod
    def get_checkpoint_interval(cls, minutes: int) -> int:
        """
        Get checkpoint save interval with demo mode compression.
        
        Args:
            minutes: Normal checkpoint interval in minutes
            
        Returns:
            int: Compressed interval in demo mode, normal interval otherwise
            
        Examples:
            >>> TimeManager.get_checkpoint_interval(5)  # Demo mode
            1
            >>> TimeManager.get_checkpoint_interval(5)  # Normal mode
            5
        """
        if DEMO_MODE:
            # Compress checkpoint interval (5 min → 30 sec)
            return max(1, (minutes * 60) // 10) // 60  # Convert to minutes
        return minutes
    
    @classmethod
    def get_approval_timeout(cls, minutes: int) -> int:
        """
        Get approval timeout with demo mode compression.
        
        Args:
            minutes: Normal approval timeout in minutes
            
        Returns:
            int: Compressed timeout in demo mode, normal timeout otherwise
            
        Examples:
            >>> TimeManager.get_approval_timeout(15)  # Demo mode
            2
            >>> TimeManager.get_approval_timeout(15)  # Normal mode
            15
        """
        if DEMO_MODE:
            # Compress approval timeout (15 min → 2 min)
            return max(1, minutes // 8)
        return minutes
    
    @classmethod
    def get_rollback_timeout(cls, minutes: int) -> int:
        """
        Get rollback timeout with demo mode compression.
        
        Args:
            minutes: Normal rollback timeout in minutes
            
        Returns:
            int: Compressed timeout in demo mode, normal timeout otherwise
            
        Examples:
            >>> TimeManager.get_rollback_timeout(5)  # Demo mode
            1
            >>> TimeManager.get_rollback_timeout(5)  # Normal mode
            5
        """
        if DEMO_MODE:
            # Compress rollback timeout (5 min → 30 sec)
            return max(1, (minutes * 60) // 10) // 60  # Convert to minutes
        return minutes
    
    @classmethod
    def format_duration(cls, td: timedelta) -> str:
        """
        Format timedelta for display.
        
        Args:
            td: timedelta to format
            
        Returns:
            str: Human-readable duration string
            
        Examples:
            >>> TimeManager.format_duration(timedelta(minutes=5))
            "5 minutes"
            >>> TimeManager.format_duration(timedelta(days=7))
            "7 days"
        """
        total_seconds = int(td.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"
    
    @classmethod
    def get_demo_phase_duration(cls, phase: str) -> timedelta:
        """
        Get expected duration for each demo phase.
        
        Args:
            phase: Demo phase name (analyze, decide, act, verify, learn)
            
        Returns:
            timedelta: Expected phase duration
        """
        # Total demo time: 10 minutes
        # Phase breakdown:
        # - analyze: 2 min (GPU Scheduler analysis)
        # - decide: 1 min (Safety Guard approval)
        # - act: 4 min (Spot Manager + Right Sizer actions)
        # - verify: 2 min (Performance monitoring)
        # - learn: 1 min (Learning Engine updates)
        
        phase_durations = {
            'analyze': timedelta(minutes=2),
            'decide': timedelta(minutes=1),
            'act': timedelta(minutes=4),
            'verify': timedelta(minutes=2),
            'learn': timedelta(minutes=1),
        }
        
        return phase_durations.get(phase, timedelta(minutes=2))
    
    @classmethod
    def get_demo_total_duration(cls) -> timedelta:
        """
        Get total expected demo duration.
        
        Returns:
            timedelta: Total demo duration (10 minutes)
        """
        return timedelta(minutes=10)
