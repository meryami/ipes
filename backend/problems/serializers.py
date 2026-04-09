from rest_framework import serializers
from .models import ProblemStatement

VALID_DOMAINS = [
    "Primary Healthcare",
    "Hospital Information Systems",
    "Electronic Health Records (EHR)",
    "Telemedicine & Digital Health",
    "Health Data Management & Analytics",
    "Medical Imaging & Diagnostics",
    "Pharmacy & Medication Management",
    "Health Insurance & Coverage",
    "Public Health Surveillance",
    "Mental Health Services",
    "Maternal & Child Health",
    "Elderly & Long-term Care",
    "Emergency Medical Services",
    "Medical Education & Training",
    "Health Policy & Governance",
    "Medical Research & Innovation",
    "Community Health",
    "Nutrition & Preventive Health",
]

VALID_SUBMITTER_TYPES = [
    "Patient / Citizen",
    "Healthcare Provider",
    "Hospital Administrator",
    "Policy Maker",
    "Researcher",
    "Technology Provider",
    "NGO / Civil Society",
    "Insurance Provider",
    "Training Institution",
    "Other",
]


class ProblemStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProblemStatement
        fields = [
            "id", "title", "description", "domain", "priority",
            "region", "submitter_type", "keywords", "word_count", "created_at",
        ]
        read_only_fields = ["id", "keywords", "word_count", "created_at"]

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters.")
        if len(value) > 255:
            raise serializers.ValidationError("Title must not exceed 255 characters.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters.")
        if len(value) > 5000:
            raise serializers.ValidationError("Description must not exceed 5000 characters.")
        return value

    def validate_domain(self, value):
        if value not in VALID_DOMAINS:
            raise serializers.ValidationError(f"Invalid domain.")
        return value

    def validate_priority(self, value):
        value = value.lower()
        if value not in ["high", "medium", "low"]:
            raise serializers.ValidationError("Priority must be high, medium, or low.")
        return value

    def validate_submitter_type(self, value):
        if value not in VALID_SUBMITTER_TYPES:
            raise serializers.ValidationError("Invalid submitter type.")
        return value
