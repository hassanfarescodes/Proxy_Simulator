import random
from assignments.models import Proxy

class OptimalCensor:
    def __init__(self):
        self.agents = []
    def run(self, step):
        if step % 10 == 0:              # Every 10 steps, pick one proxy to block
            proxies = list(Proxy.objects.filter(is_active=True, is_blocked=False))
            return random.sample(proxies, k=min(1, len(proxies)))
        return []

class AggresiveCensor(OptimalCensor):
    def run(self, step):
        if step % 10 == 0:              # Blocks two proxies every 10 steps
            proxies = list(Proxy.objects.filter(is_active=True, is_blocked=False))
            return random.sample(proxies, k=min(2, len(proxies)))
        return []

