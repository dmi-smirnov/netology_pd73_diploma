from django.db import IntegrityError
from rest_framework import serializers, status
import django.contrib.auth.password_validation
from rest_framework.exceptions import APIException

from api.models import (Address, CartPosition, Category, Order, OrderPosition,
                        ParameterName, Product, ProductParameter, Recipient,
                        Shop, ShopPosition, User)


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
        exclude = ['product']

    shop = ShopSerializer()


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ['shops']

    category = CategorySerializer()
    parameters = ProductParameterSerializer(many=True)
    shops_positions = ShopPositionSerializerWithoutProduct(many=True)


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


class CartPositionSerializerForRead(serializers.ModelSerializer):
    class Meta:
        model = CartPosition
        exclude = ['user']

    shop_position = ShopPositionSerializerForCartPosition()


class CartPositionSerializerForWrite(serializers.ModelSerializer):
    class Meta:
        model = CartPosition
        exclude = ['user']

    def is_valid(self, *, raise_exception=False):
        # Default validating
        super().is_valid(raise_exception=raise_exception)

        # Checking quantity
        if 'quantity' in self.validated_data:
            db_shop_pos = (self.instance or
                           self.validated_data.get('shop_position'))
            shop_pos_qnt = db_shop_pos.quantity
            cart_pos_qnt = self.validated_data['quantity']
            if cart_pos_qnt > shop_pos_qnt:
                error_msg = (f'The value received is {cart_pos_qnt}'
                             f', but quantity of this shop position'
                             f' is only {shop_pos_qnt}')
                
                if not self.errors.get('quantity'):
                    self._errors['quantity'] = []

                self._errors['quantity'].append(error_msg)
                
                if raise_exception:
                    raise serializers.ValidationError(self.errors)
        return not bool(self._errors)

    def create(self, validated_data):
        # Setting user from request
        if (self.context.get('request') and
            self.context['request'].user and
            self.context['request'].user.is_authenticated):
            validated_data['user'] = self.context['request'].user
        
        # Validating user field
        if not isinstance(validated_data.get('user'), User):
            errors = {
                'user': ['This field is required.']
            }
            raise serializers.ValidationError(errors)

        return super().create(validated_data)

    def save(self, **kwargs):
        try:
            return super().save(**kwargs)
        except IntegrityError as e:
            raise serializers.ValidationError(str(e))


class OrderPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPosition
        exclude = ['order']
    
    shop_position = ShopPositionSerializerForCartPosition()


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = '__all__'

    address = AddressSerializer()


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        extra_kwargs = {'user': {'write_only': True}}
    
    positions = OrderPositionSerializer(many=True, read_only=True)
    recipient = RecipientSerializer()

    def create(self, validated_data):
        copy_validated_data = validated_data.copy()

        address_validated_data =\
            copy_validated_data['recipient'].pop('address')
        recipient_validated_data = copy_validated_data.pop('recipient')
        order_validated_data = copy_validated_data
        
        # Setting user from request
        if (self.context.get('request') and
            self.context['request'].user and
            self.context['request'].user.is_authenticated):
            order_validated_data['user'] = self.context['request'].user

        # Validating user field
        if not isinstance(order_validated_data.get('user'), User):
            errors = {
                'user': ['This field is required.']
            }
            raise serializers.ValidationError(errors)

        # Setting status
        order_validated_data['status'] = Order.StatusChoices.FORMATION

        # Creating order
        db_order = super().create(order_validated_data)

        # Creating order recipient
        recipient_validated_data['order'] = db_order
        db_recipient = Recipient.objects.create(**recipient_validated_data)

        # Creating order recipient address
        address_validated_data['recipient'] = db_recipient
        Address.objects.create(**address_validated_data)

        # Getting cart positions
        db_cart_positions =\
            CartPosition.objects.filter(user=order_validated_data['user'])
        if not db_cart_positions:
            errors = {
                'error': ['Your cart is empty.']
            }
            raise serializers.ValidationError(errors,
                                              status.HTTP_404_NOT_FOUND)

        # Creating order positions
        http_error_status = status.HTTP_400_BAD_REQUEST
        for db_cart_pos in db_cart_positions:
            db_shop_pos = db_cart_pos.shop_position

            # Checking shop position
            if db_shop_pos.archived_at != None:
                errors = {
                    f'cart_position_id={db_cart_pos.pk}': {
                        f'shop_position_id={db_shop_pos.pk}': [
                            'This shop position is archived.'
                        ]
                    }
                }
                break
            if not db_shop_pos.shop.open:
                errors = {
                    f'cart_position_id={db_cart_pos.pk}': {
                        f'shop_position_id={db_shop_pos.pk}': {
                            f'shop_id={db_shop_pos.shop.pk}': [
                            'This shop is not currently accepting orders.'
                            ]
                        }
                    }
                }
                break
            if db_cart_pos.quantity > db_shop_pos.quantity:
                errors = {
                    f'cart_position_id={db_cart_pos.pk}': {
                        f'shop_position_id={db_shop_pos.pk}': [
                            f'Quantity of this cart position is'
                            f' {db_cart_pos.quantity}, but quantity'
                            f' of this shop position is currently only'
                            f' {db_shop_pos.quantity}.'
                        ]
                    }
                }
                break

            # Reservation quantity
            db_shop_pos.quantity = db_shop_pos.quantity - db_cart_pos.quantity
            try:
                db_shop_pos.save()
            except IntegrityError as e:
                errors = {
                    f'cart_position_id={db_cart_pos.pk}': {
                        f'shop_position_id={db_shop_pos.pk}': {
                            f'reservation_quantity_error': str(e)
                        }
                    }
                }
                break

            # Creating order position
            try:
                OrderPosition.objects.create(
                    order=db_order,
                    shop_position=db_shop_pos,
                    quantity=db_cart_pos.quantity
                )
            except IntegrityError as e:
                errors = {
                    f'cart_position_id={db_cart_pos.pk}': {
                        f'shop_position_id={db_shop_pos.pk}': {
                            f'creating_order_position_error': str(e)
                        }
                    }
                }
                break
        else:
            # If order positions are successfully created
            # # Deleting cart positions
            try:
                db_cart_positions.delete()
            except IntegrityError as e:
                errors = {
                    'cart_positions_deleting_error': str(e)
                }
                raise APIException(errors)

            # # Changing order status to NEW
            db_order.status = Order.StatusChoices.NEW
            try:
                db_order.save()
            except IntegrityError as e:
                errors = {
                    'order_status_changing_error': str(e)
                }
                raise APIException(errors)

            return db_order
        
        # If not all order positions created
        # # Deleting created orders positions
        for db_order_pos in db_order.positions.all():
            db_shop_pos = db_order_pos.shop_position

            # Cancel quantity reservation
            db_shop_pos.quantity =\
                db_shop_pos.quantity + db_order_pos.quantity
            try:
                db_shop_pos.save()
            except IntegrityError as e:
                http_error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                errors['quantity_reservation_cancel_error'] = {
                    f'shop_position_id={db_shop_pos.pk}': str(e)
                }

            # Deleting order position
            try:
                db_order_pos.delete()
            except IntegrityError as e:
                http_error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                errors['deleting_order_position_error'] = {
                    f'shop_position_id={db_shop_pos.pk}': str(e)
                }

        # # Deleting order
            try:
                db_order.delete()
            except IntegrityError as e:
                http_error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                errors['deleting_order_error'] = str(e)

        # # Raising exception
        raise APIException(errors, http_error_status)

    def to_representation(self, instance):
        default_data = super().to_representation(instance)

        # Adding additional data
        custom_data = default_data.copy()
        order_total_quantity: int = 0
        order_total_sum: float = 0
        for order_pos in custom_data['positions']:
            order_pos_quantity = order_pos['quantity']
            shop_position = order_pos['shop_position']
            shop_position_price = float(shop_position['price'])
            order_pos_sum =\
                shop_position_price * order_pos_quantity
            
            # Adding order position sum
            order_pos['sum'] = order_pos_sum

            order_total_quantity += order_pos_quantity

            order_total_sum += order_pos_sum
        # Adding order total quantity
        custom_data['total_quantity'] = order_total_quantity
        # Adding order total sum
        custom_data['total_sum'] = str(order_total_sum)

        return custom_data
    