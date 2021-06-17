from django.db import models

# Create your models here.

class Measurement(models.Model):
    def __str__(self):
        return 