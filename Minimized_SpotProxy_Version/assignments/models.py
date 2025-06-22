from django.db import models

class Proxy(models.Model):
    ip = models.CharField(max_length=64)
    is_test = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return self.ip

class Client(models.Model):
    ip = models.CharField(max_length=64, unique=True)
    is_censor_agent = models.BooleanField(default=False)
    known_blocked_proxies = models.IntegerField(default=0)

    def __str__(self):
        return self.ip

class Assignment(models.Model):
    proxy = models.ForeignKey(Proxy, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.client.ip} → {self.proxy.ip}"

