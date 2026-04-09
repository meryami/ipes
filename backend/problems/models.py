from django.db import models
from django.contrib.auth.models import User


class ProblemStatement(models.Model):
    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    domain = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    region = models.CharField(max_length=100, blank=True, null=True)
    submitter_type = models.CharField(max_length=50)
    keywords = models.JSONField(default=list, blank=True)
    word_count = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="submissions"
    )
    # Link to bengkel jemputan (if submitted via bengkel portal)
    jemputan = models.ForeignKey(
        "bengkel.Jemputan", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pernyataan"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
