import sys
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()
from assignments.models import Client, Proxy, Assignment
import argparse
import random
from django.db.models import F
from scripts.Censor import AggresiveCensor, TargetedCensor, MultiCensor
from scripts.config_basic import (
    BIRTH_PERIOD, SIMULATION_DURATION,
    KIND_PROFILE, STRICT_PROFILE, STATIC_PROFILES
)
from scripts.simulation_utils import request_new_proxy_new_client, update_client_credits
from django.utils.timezone import now
from datetime import timedelta

REJUVENATION_INTERVAL = 10
CENSOR_RATIO = 0.1
client_wait_start = {}
client_wait_times = []
def get_migration_proxies_ip(old_ip):
    nums = list(map(int, old_ip.split(".")))
    nums[-1] = (nums[-1] + 1) % 256
    return ".".join(map(str, nums))

def create_new_proxy(last_ip):
    nums = list(map(int, last_ip.split(".")))
    nums[-1] += 1
    new_ip = ".".join(map(str, nums))
    Proxy.objects.create(ip=new_ip, is_test=True)
    return new_ip

def create_new_client(step, client_wait_start, client_wait_times, censor_chance=CENSOR_RATIO, distributor_profile=None):
    client_ip = f"10.0.0.{Client.objects.count()+1}"
    is_censor_agent = random.random() < censor_chance

    if is_censor_agent:
        censor_tag = random.choice(['A', 'B'])
    else:
        censor_tag = None

    client = Client.objects.create(ip=client_ip, is_censor_agent=is_censor_agent, censor_tag=censor_tag)

    request_new_proxy_new_client(client, step, distributor_profile, client_wait_start, client_wait_times)
    return client

def rejuvinate(step):
    for proxy in Proxy.objects.filter(is_active=True):
        proxy.ip = get_migration_proxies_ip(proxy.ip)
        proxy.is_blocked = False
        proxy.blocked_at = None
        proxy.save()

def run_simulation(duration=BIRTH_PERIOD + SIMULATION_DURATION,
                   rejuvenation_interval=REJUVENATION_INTERVAL,
                   censor_ratio=CENSOR_RATIO,
                   distributor_profile=STRICT_PROFILE, censor_type="optimal"):
    Proxy.objects.all().delete()
    Client.objects.all().delete()
    Assignment.objects.all().delete()

    last_ip = "10.0.0.0"
    Proxy.objects.create(ip=last_ip, is_test=True)

    proxy_ratio, proxy_count, user_ratio = [], [], []
    censor_map = {
        'A': AggresiveCensor(),
        'B': TargetedCensor(),
    }

    censor = MultiCensor(censor_map)

    for step in range(duration):
        for proxy in censor.run(step):
            proxy.is_blocked = True
            proxy.blocked_at = proxy.created_at + timedelta(seconds=step)
            proxy.save()
            client_ids = Assignment.objects.filter(proxy=proxy).values_list('client_id', flat=True)
            Client.objects.filter(id__in=client_ids).update(
                known_blocked_proxies=F('known_blocked_proxies')+1
            )
            for client_id in client_ids:
                if client_id not in client_wait_start:
                    client_wait_start[client_id] = step 
            for client_id in client_ids:
                client = Client.objects.get(id=client_id)
                request_new_proxy_new_client(client, step, distributor_profile, client_wait_start, client_wait_times)

        if step % rejuvenation_interval == 0 and step > 0:
            rejuvinate(step)

        create_new_client(step, client_wait_start, client_wait_times, censor_chance=censor_ratio, distributor_profile=distributor_profile)

        if step % 3 == 0:
            last_ip = create_new_proxy(last_ip)

        if step % 5 == 0:
            old_proxies = Proxy.objects.filter(is_test=True)[:3]
            for p in old_proxies:
                p.is_active = False
                p.save()

        total_proxies = Proxy.objects.count()
        blocked_proxies = Proxy.objects.filter(is_blocked=True).count()
        proxy_ratio.append((total_proxies - blocked_proxies) / total_proxies if total_proxies else 0)
        proxy_count.append(total_proxies)
        total_users = Client.objects.count()
        blocked_users = Client.objects.filter(is_censor_agent=True).count()
        user_ratio.append((total_users - blocked_users) / total_users if total_users else 0)
        update_client_credits()

    lifetimes = [
        (proxy.blocked_at - proxy.created_at).total_seconds()
        for proxy in Proxy.objects.all() if proxy.blocked_at
    ]
    avg_lifetime = sum(lifetimes) / len(lifetimes) if lifetimes else 0

    os.makedirs("../results/", exist_ok=True)
    with open("../results/minimal_results.csv", "w") as f:
        f.write("nonblocked_proxy_ratio,nonblocked_proxy_count,connected_user_ratio,avg_proxy_lifetime\n")
        for p_ratio, p_count, u_ratio in zip(proxy_ratio, proxy_count, user_ratio):
            f.write(f"{p_ratio},{p_count},{u_ratio},{avg_lifetime}\n")

    print("Simulation complete!")

def assign_proxies_static(clients, proxies, profile):
    kind = profile["type"]
    if kind == "broadcast":
        for client in clients:
            for proxy in proxies:
                Assignment.objects.create(client=client, proxy=proxy)
    elif kind == "random":
        n = profile.get("proxies_per_client", 2)
        for client in clients:
            selected = random.sample(proxies, min(n, len(proxies)))
            for proxy in selected:
                Assignment.objects.create(client=client, proxy=proxy)
    elif kind == "fixed":
        proxy_count = len(proxies)
        for i, client in enumerate(clients):
            Assignment.objects.create(client=client, proxy=proxies[i % proxy_count])
    else:
        raise ValueError(f"Unknown profile type: {kind}")

def run_static_simulation(distributor_profile, censor_type="optimal"):
    TOTAL_CLIENTS = 100
    TOTAL_PROXIES = 10
    SIMULATION_STEPS = 30

    Proxy.objects.all().delete()
    Client.objects.all().delete()
    Assignment.objects.all().delete()

    proxies = [Proxy.objects.create(ip=f"10.0.0.{i}") for i in range(TOTAL_PROXIES)]
    clients = [Client.objects.create(ip=f"192.168.0.{i}", is_censor_agent=random.random() < CENSOR_RATIO) for i in range(TOTAL_CLIENTS)]

    assign_proxies_static(clients, proxies, distributor_profile)

    censor = TargetedCensor() if censor_type == "targeted" else OptimalCensor()
    proxy_ratio_log, user_ratio_log = [], []

    for step in range(SIMULATION_STEPS):
        for proxy in censor.run(step):
            proxy.is_blocked = True
            proxy.blocked_at = proxy.created_at + timedelta(seconds=step)
            proxy.save()
            client_ids = Assignment.objects.filter(proxy=proxy).values_list('client_id', flat=True)
            Client.objects.filter(id__in=client_ids).update(known_blocked_proxies=F('known_blocked_proxies') + 1)
            for client_id in client_ids:
                if client_id not in client_wait_start:
                    client_wait_start[client_id] = step


        total = Proxy.objects.count()
        blocked = Proxy.objects.filter(is_blocked=True).count()
        proxy_ratio = (total - blocked) / total if total else 0
        proxy_ratio_log.append(proxy_ratio)

        total_clients = Client.objects.filter(is_censor_agent=False).count()
        still_connected = sum(
            Assignment.objects.filter(client=client, proxy__is_blocked=False).exists()
            for client in Client.objects.filter(is_censor_agent=False)
        )
        user_ratio_log.append(still_connected / total_clients if total_clients else 0)

    os.makedirs("../results/", exist_ok=True)
    with open("../results/static_results.csv", "w") as f:
        f.write("proxy_ratio,connected_user_ratio\n")
        for pr, ur in zip(proxy_ratio_log, user_ratio_log):
            f.write(f"{pr},{ur}\n")

    print("Static simulation complete.")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--distributor", choices=["kind", "strict", "broadcast", "random", "fixed"], default="strict")
    parser.add_argument("--mode", choices=["dynamic", "static"], default="dynamic")
    parser.add_argument("--censor", choices=["optimal", "targeted", "snowflake"], default="optimal")

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    if args.distributor == "kind":
        profile = KIND_PROFILE
    elif args.distributor == "strict":
        profile = STRICT_PROFILE
    else:
        profile = STATIC_PROFILES[args.distributor]
    
    print(f"Running with distributor profile: {args.distributor}")

    if args.mode == "static":
        run_static_simulation(profile, censor_type=args.censor)
    else:
        run_simulation(distributor_profile=profile, censor_type=args.censor)

    avg_wait_time = sum(client_wait_times) / len(client_wait_times) if client_wait_times else 0
    print(f"\n- Average Wait Time: {round(avg_wait_time, 2)}")

