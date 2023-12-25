from django import forms
from django.core.mail import EmailMessage
from django.db import IntegrityError
from django.utils import timezone as django_timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import CreateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import yaml
from jsonschema import validate as schema_validate
from jsonschema.exceptions import ValidationError as SchemaValidationError

from api.serializers import (CartPositionSerializerForWrite,
                             CartPositionSerializerForRead,
                             OrderSerializer,
                             ParameterNameSerializer, ProductSerializer, RecipientSerializer,
                             ShopSerializer, UserSerializer)
from api.models import (CartPosition, Category, ConfirmationCode, Order,
                        Product, ProductParameter, Recipient, Shop, ShopPosition, User)


class CreateUserView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        
        created_user = serializer.instance

        send_confirmation_code_by_email(
            user=created_user,
            email_subject='Код подтверждения email'
        )

        return result


class EmailVerificationForm(forms.Form):
    email = forms.EmailField()
    confirmation_code = forms.CharField(
        min_length=ConfirmationCode.LENGTH,
        max_length=ConfirmationCode.LENGTH
    )


class EmailVerification(APIView):
    def post(self, request):
        # Validating request data fields
        errors = EmailVerificationForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_email = request.data['email']

        # Getting user from DB by email
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            resp_data = {
                'email': ['User with this email was not found.']
            }
            return Response(resp_data, status.HTTP_404_NOT_FOUND)
        
        # Checking the need for verification
        if user.email_confirmed:
            errors = {
                'email': ['This email is already verified.']
            }
            raise ValidationError(errors)

        # Getting confirmation code from DB
        try:
            db_confirmation_code = ConfirmationCode.objects.get(user=user)
        except ConfirmationCode.DoesNotExist:
            errors = {
                'error': ['Confirmation code for this user was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Confirmation code verification
        req_confirmation_code = str(request.data['confirmation_code'])
        if req_confirmation_code != db_confirmation_code.value:
            errors = {
                'confirmation_code': ['This code is invalid.']
            }
            raise ValidationError(errors)
        user.email_confirmed = True
        user.is_active = True
        user.save()
        db_confirmation_code.delete()
        resp_data = {
            'result': f'Email {req_email} verified.'
        }
        return Response(resp_data)


class UpdateUserView(UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    
class OnlyEmailForm(forms.Form):
    email = forms.EmailField()


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()
    confirmation_code = forms.CharField(
        min_length=ConfirmationCode.LENGTH,
        max_length=ConfirmationCode.LENGTH
    )
    password = forms.CharField()


class ForgotPasswordConfirmationCodeView(APIView):
    def post(self, request):
        'Requesting password change confirmation code to email'
        # Validating request data fields
        errors = OnlyEmailForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_email = request.data['email']

        # Getting user from DB
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            resp_data = {
                'email': ['User with this email was not found.']
            }
            return Response(resp_data, status.HTTP_404_NOT_FOUND)
        
        send_confirmation_code_by_email(
            user=user,
            email_subject='Код подтверждения смены пароля'
        )

        resp_data = {
            'result': f'Password change confirmation code sent to {req_email}.'
        }
        return Response(resp_data)


class ForgotPasswordView(APIView):
    def patch(self, request):
        'Password change with using confirmation code'
        # Validating request data fields
        errors = ForgotPasswordForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_data = request.data
        req_email = req_data['email']

        # Getting user from DB by email
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            errors = {
                'email': ['User with this email was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Getting confirmation code from DB
        try:
            db_confirmation_code =\
                ConfirmationCode.objects.get(user=user)
        except ConfirmationCode.DoesNotExist:
            errors = {
                'error': ['Confirmation code for this user was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Confirmation code verification
        req_confirmation_code = str(req_data['confirmation_code'])
        if req_confirmation_code != db_confirmation_code.value:
            errors = {
                'confirmation_code': ['This code is invalid.']
            }
            raise ValidationError(errors)

        # Password change
        serializer_data = {
            'password': req_data['password']
        }
        user_serializer =\
            UserSerializer(user, data=serializer_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        db_confirmation_code.delete()

        resp_data = {
            'result': ['Password changed.']
        }
        return Response(resp_data)
        

class ProductsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects\
        .exclude(shops_positions=None)\
        .filter(shops__open=True,
                shops_positions__quantity__gt=0,
                shops_positions__archived_at=None)\
        .distinct()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        default_data = super().list(request, *args, **kwargs).data

        # Filtering shop positions
        custom_data =\
            self.filter_product_shop_positions(default_data, many=True)

        return Response(custom_data)
    
    def retrieve(self, request, *args, **kwargs):
        default_data = super().retrieve(request, *args, **kwargs).data

        # Filtering shop positions
        custom_data = self.filter_product_shop_positions(default_data)

        return Response(custom_data)

    def filter_product_shop_positions(self, data: dict,
                                      many: bool = False):
        if not many:
            product_data = data.copy()
            shops_positions = product_data.pop('shops_positions')
            product_data['shops_positions'] = []
            for shop_pos_data in shops_positions:
                if (
                    shop_pos_data['quantity'] > 0 
                    and not shop_pos_data['archived_at']
                    and shop_pos_data['shop']['open']
                ):
                    product_data['shops_positions'].append(shop_pos_data)
            return product_data
        else:
            products_data = []
            for product_data in data.copy():
                products_data.append(
                    self.filter_product_shop_positions(product_data)
                )
            return products_data


class UpdateShopPositionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        yaml_file = request.FILES.get('yaml')
        if not yaml_file:
            errors = {
                'error': ['File "yaml" was not found in the request']
            }
            raise ValidationError(errors)
        
        try:
            file_data = yaml.load(yaml_file, Loader=yaml.FullLoader)
        except Exception as e:
            errors = {
                'error': ['File parsing error.']
            }
            raise ValidationError(errors)

        # Validating data schema
        schema = {
            'type': 'object',
            'properties': {
                'shop': {'type': 'string'},
                'categories': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'number'},
                            'name': {'type': 'string'}
                        },
                        'required': [
                            'id',
                            'name'
                        ]
                    }
                },
                'goods': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'number'},
                            'name': {'type': 'string'},
                            'category': {'type': 'number'},
                            'model': {'type': 'string'},
                            'description': {'type': 'string'},
                            'price': {'type': 'number'},
                            'price_rrc': {'type': 'number'},
                            'quantity': {'type': 'number'},
                            'parameters': {
                                'type': 'object'
                            }
                        },
                        'required': [
                            'id',
                            'name',
                            'category',
                            'price',
                            'quantity'
                        ]
                    }
                }
            },
            'required': [
                'shop',
                'categories',
                'goods'
            ]
        }
        try:
            schema_validate(file_data, schema)
        except SchemaValidationError as e:
            errors = {
                'file_validation_error': [e.message]
            }
            raise ValidationError(errors)

        # Validating shop
        shop_name = file_data['shop']
        try:
            shop = Shop.objects.get(name=shop_name)
        except Shop.DoesNotExist:
            errors = {
                'error': [f'Shop "{shop_name}" was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)

        # Validating user permissions
        if not request.user in shop.representatives.all():
            errors = {
                'error': [f'You are not "{shop_name}" shop representative.']
            }
            raise PermissionDenied(errors)

        file_categories_dict = dict()
        for file_category in file_data['categories']:
            file_category_id = file_category.pop('id')
            file_category_without_id = file_category
            file_categories_dict[file_category_id] = file_category_without_id

        # Validating goods categories
        for file_product in file_data['goods']:
            file_product_category = file_product['category']
            if not file_product_category in file_categories_dict.keys():
                errors = {
                    'validation_error': [
                        f'Category with id={file_product_category}'
                        f' for product with id={file_product["id"]}'
                        f' was not found in the file.'
                    ]
                }
                raise ValidationError(errors)

        # Deleting/archiving shop positions in DB
        db_shop_positions = ShopPosition.objects.filter(
            shop=shop,
            archived_at=None
        )
        for db_shop_position in db_shop_positions:
            if (db_shop_position.orders_positions.all() or
                db_shop_position.carts_positions.all()):
                db_shop_position.quantity = 0
                db_shop_position.archived_at = django_timezone.now()
                db_shop_position.save()
            else:
                db_shop_position_product = db_shop_position.product
                db_shop_position.delete()
                if not db_shop_position_product.shops_positions.all():
                    db_shop_position_product.delete()

        # Adding goods to DB
        for file_product in file_data['goods']:
            # Getting or creating category
            file_product_category_name =\
                file_categories_dict[file_product.pop('category')]['name']
            try:
                db_category, _ = Category.objects.get_or_create(
                    name=file_product_category_name)
            except IntegrityError as e:
                errors = {
                    'creating_category_error': {
                       f'name_{file_product_category_name}': e.args[0]
                    }
                }
                raise ValidationError(errors)
            
            # Creating product
            try:
                db_product = Product.objects.create(
                    name=file_product['name'],
                    model=file_product.get('model'),
                    description=file_product.get('description'),
                    category=db_category
                )
            except IntegrityError as e:
                errors = {
                    'creating_product_error': {
                       f'id_{file_product["id"]}': e.args[0]
                    }
                }
                raise ValidationError(errors)

            # Creating product parameters
            for param_name, param_value in file_product['parameters'].items():
                # Getting or creating parameter name
                serializer = ParameterNameSerializer(
                    data={'name': param_name}
                )
                serializer.is_valid()
                serializer_errors = serializer._errors
                if serializer_errors:
                    errors = {
                        'product_parameter_validation_error': {
                            f'id_{file_product["id"]}': {
                                param_name: serializer_errors
                            }
                        }
                    }
                    raise ValidationError(errors)
                db_parameter_name = serializer.save()
                
                # Creating product parameter
                try:
                    ProductParameter.objects.create(
                        product=db_product,
                        parameter_name=db_parameter_name,
                        value=param_value
                    )
                except IntegrityError as e:
                    errors = {
                        'creating_product_parameter_error': {
                            f'id_{file_product["id"]}': {
                                f'parameter_{param_name}': e.args[0]
                            }
                        }
                    }
                    raise ValidationError(errors)

            # Creating shop positon
            try:
                ShopPosition.objects.create(
                    shop=shop,
                    product=db_product,
                    external_id=file_product['id'],
                    price=file_product['price'],
                    price_rrc=file_product.get('price_rrc'),
                    quantity=file_product['quantity']
                )
            except IntegrityError as e:
                errors = {
                    'creating_shop_position_error': {
                       f'id_{file_product["id"]}': e.args[0]
                    }
                }
                raise ValidationError(errors)
            
        resp_data = {
            'status': 'Data import was successful.'
        }
        return Response(resp_data, status.HTTP_201_CREATED)


class UserCartViewSet(viewsets.mixins.CreateModelMixin,
                      viewsets.mixins.UpdateModelMixin,
                      viewsets.mixins.DestroyModelMixin,
                      viewsets.mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    queryset = CartPosition.objects.all()
    serializer_class = CartPositionSerializerForWrite
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filtering queryset by request user
        return super().get_queryset().filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        # Changing default serializer
        default_serializer = self.serializer_class
        self.serializer_class = CartPositionSerializerForRead
        default_response = super().list(request, *args, **kwargs)
        self.serializer_class = default_serializer

        # Adding additional data to response data
        cart_positions = default_response.data
        cart_total_quantity: int = 0
        cart_total_sum: float = 0
        for cart_pos in cart_positions:
            cart_pos_quantity = cart_pos['quantity']
            shop_position = cart_pos['shop_position']
            shop_position_price = float(shop_position['price'])
            
            # Adding cart position sum
            cart_pos['sum'] =\
                shop_position_price * cart_pos_quantity
            
            # Adding product shops list with
            # shop position info (id, price, quantity)
            product_id = shop_position['product']['id']
            db_product_shops_positions = ShopPosition.objects\
                .filter(product=product_id)\
                .filter(archived_at=None)\
                .exclude(quantity=0)\
                .exclude(shop__open=False)
            product_shops_data = []
            for db_shop_pos in db_product_shops_positions:
                product_shop_data = ShopSerializer(db_shop_pos.shop).data
                product_shop_data['position'] = {
                    'id': db_shop_pos.pk,
                    'price': str(db_shop_pos.price),
                    'quantity': db_shop_pos.quantity
                }
                product_shops_data.append(product_shop_data)
            cart_pos['product_shops'] = product_shops_data

            cart_total_quantity += cart_pos_quantity

            cart_total_sum += shop_position_price
        custom_data = {
            # Moving positions to subdict positions
            'positions': cart_positions,
            # Adding total quantity
            'total_quantity': cart_total_quantity,
            # Adding total sum
            'total_sum': str(cart_total_sum)
        }

        return Response(custom_data)


class UserOrdersViewSet(viewsets.mixins.CreateModelMixin,
                        viewsets.mixins.RetrieveModelMixin,
                        viewsets.mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filtering queryset by request user
        return super().get_queryset().filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        response =  super().create(request, *args, **kwargs)

        order_data = response.data
        order_num = order_data['id']

        # Sending email to customer
        email_msg = EmailMessage(
            subject=f'Создан заказ №{order_num}',
            to=(request.user.email,)
        )
        email_msg.send()

        # Sending email to admins
        admins_emails_tuples =\
            User.objects.filter(is_active=True, is_admin=True).values_list('email')
        admins_emails = set(t[0] for t in admins_emails_tuples)
        for admin_email in admins_emails:
            email_msg = EmailMessage(
                subject=f'Создан заказ №{order_num}',
                to=(admin_email,)
            )
            email_msg.send()

        return response


class RecipientsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filtering queryset by request user orders
        return super().get_queryset()\
            .filter(order__user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        default_data = super().list(request, *args, **kwargs).data

        # Deleting duplicates
        uniqs = set()
        custom_data = []
        for recipient in default_data:
            recipient_str = str(recipient)
            if recipient_str in uniqs:
                continue
            custom_data.append(recipient)
            uniqs.add(recipient_str)

        return Response(custom_data)


def create_confirmation_code(user) -> ConfirmationCode:
    try:
        user.confirmation_code.delete()
    except User.confirmation_code.RelatedObjectDoesNotExist:
        pass
    
    confirmation_code = ConfirmationCode(
        user=user,
        value=ConfirmationCode.generate()
    )
    confirmation_code.save()

    return confirmation_code

def send_confirmation_code_by_email(user, email_subject: str):
    confirmation_code = create_confirmation_code(user)
    
    email_msg = EmailMessage(
        subject=email_subject,
        body=confirmation_code.value,
        to=(user.email,)
    )
    if email_msg.send():
        confirmation_code.sent_at = django_timezone.now()
        confirmation_code.save()
