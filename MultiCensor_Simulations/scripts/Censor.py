import random
from assignments.models import Proxy, Assignment
from scripts.config_basic import SNOWFLAKE_BLOCK_INTERVAL, SNOWFLAKE_BLOCK_FRACTION

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
    def __init__(self,
                 block_interval: int = SNOWFLAKE_BLOCK_INTERVAL,
                 block_fraction: float = SNOWFLAKE_BLOCK_FRACTION):
        self.block_interval = block_interval
        self.block_fraction = block_fraction

    def run(self, step):
        if step % self.block_interval != 0:
            return []

        volunteers = list(
            Proxy.objects.filter(
                is_test=True,
                is_active=True,
                is_blocked=False
            )
        )
        if not volunteers:
            return []
        k = max(1, int(len(volunteers) * self.block_fraction))
        return random.sample(volunteers, k)

class MultiCensor:
    def __init__(self, censor_map):
        self.censor_map = censor_map
    
    def _active_proxy_ids_for_group(self, group_label):
        return list(
            Assignment.objects.filter(
                proxy__is_blocked=False,
                client__is_censor_agent=False,
                client__censor_group=group_label
            ).values_list('proxy_id', flat=True).distinct()
        )

    def _choose_for_censor(self, censor, active_ids, step):
        if not active_ids:
            return []
        cname = censor.__class__.__name__

        if cname == "OptimalCensor":
            if step % 10 == 0:
                ids = random.sample(active_ids, k=min(1, len(active_ids)))
                return list(Proxy.objects.filter(id__in=ids))
            return []

        if cname == "AggresiveCensor":
            if step % 10 == 0:
                ids = random.sample(active_ids, k=min(2, len(active_ids)))
                return list(Proxy.objects.filter(id__in=ids))
            return []

        if cname == "TargetedCensor":
            qs = Proxy.objects.filter(id__in=active_ids, is_active=True, is_blocked=False)
            scores = []
            for proxy in qs:
                honest_users = Assignment.objects.filter(
                    proxy=proxy, client__is_censor_agent=False
                ).count()
                scores.append((honest_users, proxy.id))
            if not scores:
                return []
            scores.sort(key=lambda x: (x[0], x[1]), reverse=True)
            k = max(1, len(scores) // 10)
            top_ids = [pid for _, pid in scores[:k]]
            return list(Proxy.objects.filter(id__in=top_ids))

        if cname == "SnowflakeCensor":
            interval = getattr(censor, "block_interval", 10)
            frac = getattr(censor, "block_fraction", 0.1)
            if step % interval != 0:
                return []
            candidates = list(Proxy.objects.filter(
                id__in=active_ids, is_active=True, is_blocked=False, is_test=True
            ))
            if not candidates:
                return []
            k = max(1, int(len(candidates) * frac))
            return random.sample(candidates, k=min(k, len(candidates)))

        return []

    def run(self, step):
        all_to_block = []
        for group_label, censor in self.censor_map.items():
            active_ids = self._active_proxy_ids_for_group(group_label)
            picks = self._choose_for_censor(censor, active_ids, step)
            if picks:
                all_to_block.extend(picks)
        by_id = {p.id: p for p in all_to_block}
        return list(by_id.values())
