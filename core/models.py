from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """Base model with common fields for all models."""
    
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']

