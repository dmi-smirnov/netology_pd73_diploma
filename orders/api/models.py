import random
import string
from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from rest_framework.fields import MinValueValidator


class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str):
        '''
        Creates and saves a User with the given email and password.
        '''
        if not email:
            raise ValueError('Users must have an email address')
        if not password:
            raise ValueError('Users must have a password')
        
        user = self.model(
            email=self.normalize_email(email)
        )

        user.set_password(password)
        
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, email: str, password: str):
        '''
        Creates and saves a superuser with the given email and password.
        '''
        user = self.create_user(
            email,
            password=password
        )

        user.is_active = True
        user.is_admin = True

        user.save(using=self._db)

        return user

class User(AbstractBaseUser):
    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'

    email = models.EmailField(
        verbose_name='email',
        max_length=255,
        unique=True,
    )
    email_confirmed = models.BooleanField(default=False)

    is_active = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"

    first_name = models.CharField(max_length=30, verbose_name='имя')
    last_name = models.CharField(max_length=30, verbose_name='фамилия')
    patronymic = models.CharField(max_length=30, verbose_name='отчество')

    company = models.CharField(max_length=50, verbose_name='компания')
    position = models.CharField(max_length=50, verbose_name='должность')

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        'Does the user have a specific permission?'
        # Yes, always
        return True

    def has_module_perms(self, app_label):
        'Does the user have permissions to view the app `app_label`?'
        # Yes, always
        return True

    @property
    def is_staff(self):
        # All admins are staff
        return self.is_admin
    
    @classmethod
    def get_required_fields_names(cls) -> set[str]:
        fields = cls._meta.get_fields()
        required_fields = set()
        for field in fields:
            if getattr(field, 'blank', True):
                continue
            if field.has_default():
                continue
            field_name = getattr(field, 'attname', None)
            if field_name:
                required_fields.add(field_name)
        return required_fields
    

class ConfirmationCode(models.Model):
    class Meta:
        verbose_name = 'код подтверждения'
        verbose_name_plural = 'коды подтверждения'

    LENGTH = 10
    LETTERS = string.digits

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='confirmation_code'
    )
    value = models.CharField(max_length=LENGTH, verbose_name='значение')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='создан')
    sent_at = models.DateTimeField(null=True,
                                   verbose_name='отправлен')
    
    @classmethod
    def generate(cls):
        code = ''.join(random.choice(cls.LETTERS) for _ in range(cls.LENGTH))
        return code


class Order(models.Model):
    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'

    class StatusChoices(models.TextChoices):
        FORMATION = ('FORMATION', 'Формируется')
        NEW = ('NEW', 'Новый')
        CONFIRMED = ('CONFIRMED', 'Подтверждён')
        ASSEMBLED = ('ASSEMBLED', 'Собран')
        SENT = ('SENT', 'Отправлен')
        DELIVERED = ('DELIVERED', 'Доставлен')
        CANCELED = ('CANCELED', 'Отменён')

    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='создан')
    delivired_at = models.DateTimeField(verbose_name='доставлен', null=True,
                                        blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        blank=True,
        verbose_name='статус'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        related_name='orders',
        verbose_name='пользователь'
    )

    def __str__(self):
        return f'№{self.pk} (id={self.pk})'


class Recipient(models.Model):
    class Meta:
        verbose_name = 'получатель заказа'
        verbose_name_plural = 'получатели заказа'
    
    first_name = models.CharField(max_length=30, verbose_name='имя')
    last_name = models.CharField(max_length=30, verbose_name='фамилия')
    patronymic = models.CharField(max_length=30, verbose_name='отчество')
    email = models.EmailField(max_length=50, verbose_name='эл. почта')
    phone = models.CharField(max_length=20, verbose_name='телефон')
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        primary_key=True,
        blank=True,
        related_name='recipient',
        verbose_name='заказ'
    )

    def __str__(self):
        return (f'{self.last_name} {self.first_name} {self.patronymic}'
                f' (id={self.pk})')


class Address(models.Model):
    class Meta:
        verbose_name = 'адрес'
        verbose_name_plural = 'адреса'
    
    city = models.CharField(max_length=50, verbose_name='город')
    street = models.CharField(max_length=50, verbose_name='улица')
    house_number = models.CharField(max_length=10, verbose_name='дом')
    house_block = models.CharField(max_length=10, verbose_name='корпус')
    house_building = models.CharField(max_length=10, verbose_name='строение')
    appartment = models.CharField(max_length=10, verbose_name='квартира')
    recipient = models.OneToOneField(
        Recipient,
        on_delete=models.CASCADE,
        primary_key=True,
        blank=True,
        related_name='address',
        verbose_name='получатель заказа'
    )


class ParameterName(models.Model):
    class Meta:
        verbose_name = 'название параметра'
        verbose_name_plural = 'названия параметров'

    name = models.CharField(max_length=40, verbose_name='название')


class Category(models.Model):
    class Meta:
        verbose_name = 'категория товара'
        verbose_name_plural = 'категории товара'

    name = models.CharField(max_length=40, verbose_name='название',
                            unique=True)
    
    def __str__(self):
        return f'{self.name} (id={self.pk})'


class Shop(models.Model):
    class Meta:
        verbose_name = 'магазин'
        verbose_name_plural = 'магазины'
    
    name = models.CharField(max_length=40, verbose_name='название')
    open = models.BooleanField(verbose_name='приём заказов')
    representatives = models.ManyToManyField(
        User,
        related_name='shops',
        verbose_name='представители',
        blank=True
    )

    def __str__(self):
        return f'{self.name} (id={self.pk})'


class Product(models.Model):
    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    name = models.CharField(max_length=80, verbose_name='название')
    description = models.CharField(max_length=40, verbose_name='описание',
                                   null=True)
    model = models.CharField(max_length=40, verbose_name='модель',
                             null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='категория'
    )
    shops = models.ManyToManyField(
        Shop,
        through='ShopPosition',
        related_name='products',
        verbose_name='магазины',
        blank=True
    )

    def __str__(self):
        return f'{self.name} (id={self.pk})'


class ProductParameter(models.Model):
    class Meta:
        verbose_name = 'параметр товара'
        verbose_name_plural = 'параметры товара'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'parameter_name'],
                name='unique_product_parameter_name'
            )
        ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='parameters',
        verbose_name='товар'
    )
    parameter_name = models.ForeignKey(
        ParameterName,
        on_delete=models.CASCADE,
        verbose_name='название'
    )
    value = models.CharField(max_length=50, verbose_name='значение')


class ShopPosition(models.Model):
    class Meta:
        verbose_name = 'позиция в магазине'
        verbose_name_plural = 'позиции в магазине'
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'product', 'external_id', 'archived_at'],
                name='unique_shop_product'
            )
        ]

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='positions',
        verbose_name='магазин'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='shops_positions',
        verbose_name='товар'
    )
    external_id = models.PositiveIntegerField(verbose_name='внешний ID')
    price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='цена'
    )
    price_rrc = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='рекомендуемая розничная цена',
        null=True
    )
    quantity = models.PositiveIntegerField(verbose_name='количество')
    archived_at = models.DateTimeField(verbose_name='архивирован', null=True,
                                       blank=True)

    def __str__(self):
        return f'{self.product.name}, {self.shop.name} (id={self.pk})'


class CartPosition(models.Model):
    class Meta:
        verbose_name = 'позиция в корзине'
        verbose_name_plural = 'позиции в корзине'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'shop_position'],
                name='unique_user_cart_shop_position'
            )
        ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cart_positions',
        verbose_name='пользователь',
        blank=True
    )
    shop_position = models.ForeignKey(
        ShopPosition,
        on_delete=models.CASCADE,
        related_name='carts_positions',
        verbose_name='позиция в магазине'
    )
    quantity = models.PositiveIntegerField(verbose_name='количество')


class OrderPosition(models.Model):
    class Meta:
        verbose_name = 'позиция в заказе'
        verbose_name_plural = 'позиции в заказе'
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'shop_position'],
                name='unique_order_shop_position'
            )
        ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='positions',
        verbose_name='заказ'
    )
    shop_position = models.ForeignKey(
        ShopPosition,
        on_delete=models.CASCADE,
        related_name='orders_positions',
        verbose_name='позиция в магазине'
    )
    quantity = models.PositiveIntegerField(verbose_name='количество')


def get_model_concrete_fields_names(M) -> list:
    return [f.name for f in M._meta.concrete_fields]