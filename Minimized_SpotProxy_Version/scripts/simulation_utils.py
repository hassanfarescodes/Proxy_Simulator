from assignments.models import Client, Proxy, Assignment
from scripts.logger import rblog
import logging

def score_proxy_for_client(proxy, client, distributor_profile):
    # Pull weight factors
    alpha1 = distributor_profile.get("alpha1", 1)
    alpha2 = distributor_profile.get("alpha2", 1)
    alpha3 = distributor_profile.get("alpha3", 1)
    alpha4 = distributor_profile.get("alpha4", 1)
    alpha5 = distributor_profile.get("alpha5", 1)

    # Example input features (replace with real logic if needed)
    proxy_usage = Assignment.objects.filter(proxy=proxy).count()
    client_requests = client.known_blocked_proxies
    location_penalty = 1  # Placeholder if you want IP-distance logic

    # Scoring formula: Higher score = better proxy for this client
    score = (
        alpha1 * (proxy_usage)
        - alpha2 * (client_requests)
        - alpha3 * (client.known_blocked_proxies)
        - alpha5 * (location_penalty)
    )
    return score


def request_new_proxy_new_client(client, step, distributor_profile):
    active_proxies = Proxy.objects.filter(is_active=True, is_blocked=False)

    if not active_proxies.exists():
        return

    best_proxy = None
    best_score = float('-inf')

    for proxy in active_proxies:
        score = score_proxy_for_client(proxy, client, distributor_profile)
        if score > best_score:
            best_score = score
            best_proxy = proxy

    if best_proxy:
        Assignment.objects.create(client=client, proxy=best_proxy)

def update_client_credits():
    for client in Client.objects.all():
        assignments = Assignment.objects.filter(client=client).select_related('proxy')
        earned = 0
        for a in assignments:
            if not a.proxy.is_blocked:
                client.credits += 0.1
                earned += 0.1
        client.save()
        
        if earned > 0:
            rblog.debug(f"Client {client.ip} earned {earned:.2f} credits, total now {client.credits:.2f}")

CREDIT_COST = 1.0

def request_new_proxy_new_client(client, step, distributor_profile):
    # Check if client has never been assigned a proxy
    has_any_assignment = Assignment.objects.filter(client=client).exists()
    if not has_any_assignment or client.credits >= CREDIT_COST:
        active_proxies = Proxy.objects.filter(is_active=True, is_blocked=False)
        if not active_proxies.exists():
            return

        best_proxy = None
        best_score = float('-inf')

        for proxy in active_proxies:
            score = score_proxy_for_client(proxy, client, distributor_profile)
            if score > best_score:
                best_score = score
                best_proxy = proxy

        if best_proxy:
            Assignment.objects.create(client=client, proxy=best_proxy)
            if has_any_assignment:
                client.credits -= CREDIT_COST  # Only charge if not the first proxy
            client.save()
