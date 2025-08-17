# news/models.py
from django.db import models

class News(models.Model):
    title = models.CharField(max_length=255)
    link = models.URLField(unique=True)
    description = models.TextField()
    source = models.CharField(max_length=100)
    image_url = models.URLField(null=True, blank=True) 
    published = models.DateTimeField()
    
    class Meta:
        ordering = ['-published'] 

    def __str__(self):
        return self.title
