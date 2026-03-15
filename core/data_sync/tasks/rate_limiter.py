"""
速率限制器
"""
import time
from collections import deque


class RateLimiter:
    """API 速率限制器"""
    
    def __init__(self, max_requests_per_minute: int = 500):
        self.max_requests = max_requests_per_minute
        self.request_times = deque()
        self.min_interval = 60.0 / max_requests_per_minute if max_requests_per_minute > 0 else 0
    
    def wait_if_needed(self):
        """检查并等待，确保不超过速率限制"""
        now = time.time()
        
        # 清理1分钟前的记录
        while self.request_times and self.request_times[0] < now - 60:
            self.request_times.popleft()
        
        # 如果达到限制，等待
        if len(self.request_times) >= self.max_requests:
            sleep_time = 60 - (now - self.request_times[0])
            if sleep_time > 0:
                print(f"   ⏱️  速率限制: 等待 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)
        
        # 最小间隔控制
        if self.request_times:
            last_request_time = self.request_times[-1]
            elapsed = now - last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
        
        # 记录本次请求时间
        self.request_times.append(time.time())
