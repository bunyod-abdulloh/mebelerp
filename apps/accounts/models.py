from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Rahbar"
        MANAGER = "manager", "Menejer"
        WORKER = "worker", "Xodim"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.WORKER)
    phone = models.CharField(max_length=20, blank=True)

    @property
    def is_owner(self) -> bool:
        return self.role == self.Role.OWNER

    def __str__(self):
        return self.get_full_name() or self.username
