# app/utils/memory.py
import gc
import logging
import psutil
import os

logger = logging.getLogger(__name__)

def get_memory_usage():
    """Get current memory usage"""
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # in MB
    except Exception as e:
        logger.error(f"Failed to get memory usage: {str(e)}")
        return 0

def optimize_memory():
    """Safely optimize memory usage"""
    try:
        before = get_memory_usage()
        gc.collect()
        after = get_memory_usage()
        logger.info(f"Memory optimization: {before:.2f}MB -> {after:.2f}MB")
        return True
    except Exception as e:
        logger.error(f"Memory optimization failed: {str(e)}")
        return False

def check_memory_threshold(threshold_mb=500):
    """Check if memory usage is above threshold"""
    try:
        usage = get_memory_usage()
        if usage > threshold_mb:
            logger.warning(f"Memory usage ({usage:.2f}MB) exceeds threshold ({threshold_mb}MB)")
            return False
        return True
    except Exception as e:
        logger.error(f"Memory check failed: {str(e)}")
        return True  # Return True on error to avoid false alarms