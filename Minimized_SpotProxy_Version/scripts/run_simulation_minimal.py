import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from random import random
from django.db.models import F
from assignments.models import Client, Proxy, Assignment
from scripts.Censor import OptimalCensor
from scripts.config_basic import BIRTH_PERIOD, SIMULATION_DURATION
from scripts.simulation_utils import request_new_proxy_new_client


REJUVENATION_INTERVAL = 10
CENSOR_RATIO = 0.1

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

def create_new_client(step, censor_chance=CENSOR_RATIO):
    client_ip = f"10.0.0.{Client.objects.count()+1}"
    is_censor_agent = random() < censor_chance
    client = Client.objects.create(ip=client_ip, is_censor_agent=is_censor_agent)
    request_new_proxy_new_client(client, step)
    return client

def rejuvinate(step):
    for proxy in Proxy.objects.filter(is_active=True):
        proxy.ip = get_migration_proxies_ip(proxy.ip)
        proxy.is_blocked = False
        proxy.save()

def run_simulation(
    duration=BIRTH_PERIOD + SIMULATION_DURATION,
    rejuvenation_interval=REJUVENATION_INTERVAL,
    censor_ratio=CENSOR_RATIO
):
    Proxy.objects.all().delete()
    Client.objects.all().delete()
    Assignment.objects.all().delete()

    last_ip = "10.0.0.0"
    Proxy.objects.create(ip=last_ip, is_test=True)

    proxy_ratio, proxy_count, user_ratio = [], [], []
    censor = OptimalCensor()

    for step in range(duration):
        # Block some proxies
        for proxy in censor.run(step):
            proxy.is_blocked = True
            proxy.save()
            # mark all clients of this proxy as knowing it's blocked
            client_ids = Assignment.objects.filter(proxy=proxy).values_list('client_id', flat=True)
            Client.objects.filter(id__in=client_ids).update(
                known_blocked_proxies=F('known_blocked_proxies')+1
            )

        # Rejuvenate proxies
        if step % rejuvenation_interval == 0 and step > 0:
            rejuvinate(step)

        # Create new client
        create_new_client(step, censor_chance=censor_ratio)

        # Add new proxy every 5 steps
        if step % 5 == 0:
            last_ip = create_new_proxy(last_ip)

        total_proxies = Proxy.objects.count()
        blocked_proxies = Proxy.objects.filter(is_blocked=True).count()
        proxy_ratio.append((total_proxies - blocked_proxies) / total_proxies if total_proxies else 0)
        proxy_count.append(total_proxies)
        total_users = Client.objects.count()
        blocked_users = Client.objects.filter(is_censor_agent=True).count()
        user_ratio.append((total_users - blocked_users) / total_users if total_users else 0)

    # THis will save the results to a csv file
    os.makedirs("../results/", exist_ok=True)
    with open("../results/minimal_results.csv", "w") as f:
        f.write("nonblocked_proxy_ratio,nonblocked_proxy_count,connected_user_ratio\n")
        for p_ratio, p_count, u_ratio in zip(proxy_ratio, proxy_count, user_ratio):
            f.write(f"{p_ratio},{p_count},{u_ratio}\n")

    print("Simulation complete!")

if __name__ == "__main__":
    run_simulation()

