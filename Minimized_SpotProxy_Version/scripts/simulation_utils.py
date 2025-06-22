from assignments.models import Proxy, Assignment

def request_new_proxy_new_client(client, step):
    # Assign this client a proxy if there's one active
    proxy = Proxy.objects.filter(is_active=True, is_blocked=False).order_by("?").first()
    if proxy:
        Assignment.objects.create(client=client, proxy=proxy)

