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


from api.serializers import (ParameterNameSerializer, ProductSerializer,
                             UserSerializer)
from api.models import (Category, ConfirmationCode, Product, ProductParameter,
                        Shop, ShopPosition, User)


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
        

class ProductsView(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects\
        .exclude(shops_positions=None)\
        .exclude(shops__open=False)\
        .exclude(shops_positions__quantity=0)\
        .filter(shops_positions__archived_at=None)
        
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]


class UpdateShopView(APIView):
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
                shop_position = ShopPosition.objects.create(
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
