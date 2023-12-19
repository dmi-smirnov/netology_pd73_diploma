from django.db import IntegrityError
from rest_framework import serializers
import django.contrib.auth.password_validation

from api.models import (CartPosition, Category, ParameterName, Product,
                        ProductParameter, Shop, ShopPosition, User)


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


class ParameterNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterName
        exclude = ['id']


class ProductParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductParameter
        exclude = ['id', 'product']

    parameter_name = ParameterNameSerializer()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        exclude = ['id']


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        exclude = ['representatives']


class ShopPositionSerializerWithoutProduct(serializers.ModelSerializer):
    class Meta:
        model = ShopPosition
        exclude = ['archived_at', 'product']

    shop = ShopSerializer()


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

    category = CategorySerializer()
    parameters = ProductParameterSerializer(many=True)
    shops_positions = ShopPositionSerializerWithoutProduct(many=True)
    shops = ShopSerializer(many=True)


class ProductSerializerForCartPosition(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ['shops']

    category = CategorySerializer()
    parameters = ProductParameterSerializer(many=True)


class ShopPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopPosition
        exclude = ['archived_at']

    shop = ShopSerializer()
    product = ProductSerializer()


class ShopPositionSerializerForCartPosition(serializers.ModelSerializer):
    class Meta:
        model = ShopPosition
        exclude = ['archived_at']

    shop = ShopSerializer()
    product = ProductSerializerForCartPosition()


class CartPositionSerializerForList(serializers.ModelSerializer):
    class Meta:
        model = CartPosition
        exclude = ['user']

    shop_position = ShopPositionSerializerForCartPosition()


class CartPositionSerializerForCreate(serializers.ModelSerializer):
    class Meta:
        model = CartPosition
        exclude = ['user']

    def save(self, **kwargs):
        try:
            return super().save(**kwargs)
        except IntegrityError as e:
            raise serializers.ValidationError(str(e))
