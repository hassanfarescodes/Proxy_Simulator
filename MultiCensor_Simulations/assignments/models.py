from django.db import models

class Proxy(models.Model):
    ip = models.CharField(max_length=64)
    is_test = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    blocked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.ip

class Client(models.Model):
    ip = models.CharField(max_length=64, unique=True)
    is_censor_agent = models.BooleanField(default=False)
    known_blocked_proxies = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    censor_group = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B')],
        default='A',
        db_index=True,
    )
    credits = models.FloatField(default=0.0)


    def __str__(self):
        return self.ip

class Assignment(models.Model):
    proxy = models.ForeignKey(Proxy, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client.ip} → {self.proxy.ip}"
