"""
DRF serializers for Tender Trail.

Because tenders live in MongoDB via MongoEngine (not Django's ORM), we use
plain ``rest_framework.serializers.Serializer`` subclasses with explicit
create/update logic instead of ModelSerializer, which only understands
Django model instances.
"""

from rest_framework import serializers

from .models import Tender, TenderWatch, AlertPreference, CATEGORY_CHOICES, INDIAN_STATES


class TenderSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    reference_no = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=500)
    department = serializers.CharField(max_length=300)
    category = serializers.ChoiceField(choices=CATEGORY_CHOICES, default="Other")
    state = serializers.ChoiceField(choices=INDIAN_STATES, default="PAN India")
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    estimated_value = serializers.FloatField(required=False, default=0.0)
    emd_amount = serializers.FloatField(required=False, default=0.0)
    publish_date = serializers.DateTimeField(required=False)
    deadline = serializers.DateTimeField()
    opening_date = serializers.DateTimeField(required=False, allow_null=True)
    source_portal = serializers.CharField(required=False, allow_blank=True)
    source_url = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(read_only=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    days_remaining = serializers.SerializerMethodField()

    def get_days_remaining(self, obj):
        if isinstance(obj, Tender):
            return obj.days_remaining()
        return None

    def to_representation(self, instance):
        # instance is a mongoengine Document; map .id to str explicitly.
        ret = super().to_representation(instance)
        ret["id"] = str(instance.id)
        return ret

    def create(self, validated_data):
        tender = Tender(**validated_data)
        tender.save()
        tender.refresh_status()
        return tender

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.refresh_status()
        return instance


class TenderWatchSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    keyword = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    min_value = serializers.FloatField(required=False, default=0.0)
    max_value = serializers.FloatField(required=False, default=0.0)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret["id"] = str(instance.id)
        return ret

    def create(self, validated_data):
        user_id = self.context["request"].user.id
        watch = TenderWatch(user_id=user_id, **validated_data)
        watch.save()
        return watch

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AlertPreferenceSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    enabled = serializers.BooleanField(default=True)
    remind_days_before = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
    categories = serializers.ListField(child=serializers.CharField(), required=False)
    states = serializers.ListField(child=serializers.CharField(), required=False)

    def create(self, validated_data):
        user_id = self.context["request"].user.id
        pref, _ = AlertPreference.get_or_create_for_user(user_id)
        for attr, value in validated_data.items():
            setattr(pref, attr, value)
        pref.save()
        return pref

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance