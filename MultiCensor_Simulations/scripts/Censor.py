import random
from assignments.models import Proxy, Assignment

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

class TargetedCensor:
    def run(self, step):
        active_proxies = Proxy.objects.filter(is_active=True, is_blocked=False)

        proxy_scores = []
        for proxy in active_proxies:
            honest_users = Assignment.objects.filter(proxy=proxy, client__is_censor_agent=False).count()
            proxy_scores.append((honest_users, proxy))

        proxy_scores.sort(key=lambda x: (x[0], x[1].id), reverse=True)
        to_block = [p for _, p in proxy_scores[:max(1, len(proxy_scores) // 10)]]
        return to_block

class SnowflakeCensor:
    def run(self, step):
        if step % 10 == 0:
            proxies = list(Proxy.objects.filter(is_active=True, is_blocked=False))
            blocked_count = int(len(proxies) * 0.05)
            return random.sample(proxies, k=min(blocked_count, len(proxies)))
        return []

class MultiCensor:
    def __init__(self, censor_map):
        self.censor_map = censor_map

    def run(self, step):
        all_to_block = []
        for _, censor in self.censor_map.items():
            blocked = censor.run(step)
            all_to_block.extend(blocked)
        return list(set(all_to_block))

