# accounts/api/serializers/custom_user_serializers.py

"""
Serializers for CustomUser model.
Includes both full and minimal serializer representations.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models.custom_user import UserContact
from core.models import Country

CustomUser = get_user_model()


class UserContactMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for UserContact model."""

    class Meta:
        model = UserContact
        fields = [
            "id",
            "city",
            "state",
            "country",
            "timezone",
        ]


class UserContactSerializer(serializers.ModelSerializer):
    """Full serializer for UserContact model."""

    country_name = serializers.SerializerMethodField()

    class Meta:
        model = UserContact
        fields = [
            "id",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "country_name",
            "contact_info",
            "timezone",
            "availability",
        ]

    def get_country_name(self, obj):
        if obj.country:
            return obj.country.name
        return None


class CustomUserMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for CustomUser model."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "is_active",
        ]
        read_only_fields = fields


class CustomUserSerializer(serializers.ModelSerializer):
    """Full serializer for CustomUser model."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    contact = UserContactSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "profile_picture",
            "email_verified",
            "phone_verified",
            "two_factor_enabled",
            "last_password_change",
            "last_active",
            "login_count",
            "date_joined",
            "is_active",
            "contact",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_active",
            "login_count",
            "email_verified",
            "phone_verified",
            "last_password_change",
        ]

    def create(self, validated_data):
        """Create new user with contact information."""
        contact_data = self.context.get("contact_data", {})
        user = CustomUser.objects.create_user(**validated_data)

        if contact_data:
            UserContact.objects.create(user=user, **contact_data)

        return user

    def update(self, instance, validated_data):
        """Update user and related contact if provided."""
        contact_data = self.context.get("contact_data")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if contact_data and hasattr(instance, "contact"):
            contact = instance.contact
            for attr, value in contact_data.items():
                setattr(contact, attr, value)
            contact.save()

        return instance
