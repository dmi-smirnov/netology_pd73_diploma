from rest_framework import serializers
import django.contrib.auth.password_validation

from api.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = list(User.get_required_fields_names())
        extra_kwargs = {'password': {'write_only': True}}

    def validate_password(self, value):
        django.contrib.auth.password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        raw_pwd = validated_data.pop('password')

        instance = super().create(validated_data)

        instance.set_password(raw_pwd)
        instance.save()

        return instance
    
    def update(self, instance, validated_data):
        if 'password' in validated_data:
            raw_pwd = validated_data.pop('password')
            instance.set_password(raw_pwd)
        
        return super().update(instance, validated_data)
