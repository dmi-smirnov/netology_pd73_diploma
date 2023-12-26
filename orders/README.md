# netology_pd73_diploma

## Подготовка файла с переменными окружения
В директории проекта создать файл `.env` со следующими переменными окружения:
```
PROJECT_NAME='netology_pd73_diploma'

SECRET_KEY='...'
DEBUG=

DB_ENGINE='django.db.backends.postgresql'
DB_PORT='5432'
DB_USER=${PROJECT_NAME}
DB_PWD='...'
DB_NAME=${PROJECT_NAME}

EMAIL_HOST='...'
EMAIL_PORT='...'
EMAIL_USE_SSL=1
EMAIL_HOST_USER='...'
EMAIL_HOST_PASSWORD='...'
DEFAULT_FROM_EMAIL='...'

HTTP_SRV_ADDR_PORT='127.0.0.1:80'
```
`SECRET_KEY='...'` вместо `...` подставить SECRET KEY для Django

`DEBUG=` режим DEBUG (любое значение для включения)

`DB_PWD='...'` вместо `...` подставить пароль, который будет использоваться для БД

`HTTP_SRV_ADDR_PORT='127.0.0.1:80'` адрес и порт, по которым будет доступно приложение на хосте

`EMAIL_HOST='...'` вместо `...` подставить адрес сервера эл. почты

`EMAIL_PORT='...'` вместо `...` подставить порт сервера эл. почты

`EMAIL_USE_SSL=1` использование SSL

`EMAIL_HOST_USER='...'` вместо `...` подставить имя пользователя эл. почты

`EMAIL_HOST_PASSWORD='...'` вместо `...` подставить пароль эл. почты

`DEFAULT_FROM_EMAIL='...'` вместо `...` подставить адрес эл. почты

## Запуск контейнеров для приложения
Из директории проекта выполнить:
```bash
sudo docker compose up -d
```

## Создание административного пользователя
- После запуска контейнеров выполнить из директории проекта:
```bash
sudo docker compose ps
```
- Скопировать имя контейнера для сервиса `gunicorn_django`
- Подключиться к контейнеру, выполнив из директории проекта:
```bash
sudo docker exec -it container_name bash
```
- В контейнере выполнить:
```bash
python manage.py createsuperuser
```
- Ввести запрашиваемые `Email` и `Password`

## Административный сайт
- Маршрут: `admin`  
- Функционал:
  - работа с сущностями:
    - пользователи
    - токены пользователей
    - магазины и их представители
    - категории товаров
    - товары
    - позиции магазинов
    - позиции корзин пользователей
    - получатели заказа
    - адреса получателей заказов
    - заказы
    - позиции заказов


## API

### Регистрация пользователя
- Запрос
  - Маршрут: `api/signup`  
  - Метод: `POST`  
  - `JSON`:
    - email
    - password
    - first_name
    - last_name
    - patronymic
    - company
    - position
- Ответ:
  - Код: `201`
- Результат:
  - создан пользователь
  - отправлен код подтверждения email

### Подтверждение email
- Запрос
  - Маршрут: `api/verify_email`
  - Метод: `POST`
  - `JSON`:
    - email
    - confirmation_code
- Ответ:
  - Код: `200`
  - `JSON`:
    - result: Email {user_email} verified.
- Результат:
  - email пользователя подтверждён
  - пользователь активирован

### Запрос кода подтверждения для смены забытого пароля
- Запрос
  - Маршрут: `api/forgot_password/confirmation_code`
  - Метод: `post`
  - `JSON`:
    - email
- Ответ:
  - Код: `200`
  - `JSON`:
    - result: Password change confirmation code sent to {user_email}.
- Результат:
  - отправлен код подтверждения для смены забытого пароля на указанный email

### Смены забытого пароля
- Запрос
  - Маршрут: `api/forgot_password`
  - Метод: `PATCH`
  - `JSON`:
    - email
    - confirmation_code
    - password
- Ответ:
  - Код: `200`
  - `JSON`:
    - result: [ Password changed. ]
- Результат:
  - пароль изменён на указанный

### Авторизация (получение токена)
- Запрос
  - Маршрут: `api/signin`
  - Метод: `POST`
  - `JSON`:
    - username (email)
    - password
- Ответ:
  - Код: `200`
  - `JSON`:
    - token
- Результат:
  - создан токен, если ранее не создавался

### Обновление позиций магазина представителем магазина
- Обязательные условия
  - магазин существует
  - пользователь является представителем магазина
- Запрос
  - Маршрут: `api/user/shops/update_positions`
  - Метод: `POST`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - `FILES`:
    - yaml
- Ответ:
  - Код: `201`
  - `JSON`:
    - status: Data import was successful.
- Результат:
  - Существующие позиции магазина:
    - удалены, если не используются в позициях заказов или в позициях корзин пользователей
    - обнулены и архивированы, если используются в позициях заказов или в позициях корзин пользователей
  - Удалены товары удалённых позиций магазина, если эти товары не используются в других позициях магазинов
  - Для каждой позиции магазина из файла:
    - создана категория, если ранее такой не существовало
    - создан товар
    - созданы параметры для товара


### Получение списка товаров
- Запрос
  - Маршрут: `api/products`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - Параметры (необязательные):
    - name (фильтрация по названию)
    - model (фильтрация по модели)
    - search (поиск по названию, модели, описанию, названию категории)
- Ответ:
  - Код: `200`
  - `JSON []`:
    - id
    - name
    - description
    - model
    - category
      - name
    - parameters []
      - parameter_name
        - name
      - value
    - shops_positions []
      - id
      - shop
        - id
        - name
        - open
      - external_id
      - price
      - price_rrc
      - quantity
      - archived_at
- Результат:
  - возвращён список товаров с позициями магазинов, которые:
    - имеются в наличии
    - не архивированы
    - магазин принимает заказы

### Получение товара по id
- Запрос
  - Маршрут: `api/products/<product_id>`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `200`
  - `JSON`:
    - id
    - name
    - description
    - model
    - category
      - name
    - parameters []
      - parameter_name
        - name
      - value
    - shops_positions []
      - id
      - shop
        - id
        - name
        - open
      - external_id
      - price
      - price_rrc
      - quantity
      - archived_at
- Результат:
  - возвращён товар с позициями магазинов, которые:
    - имеются в наличии
    - не архивированы
    - магазин принимает заказы

### Получение корзины пользователя
- Запрос
  - Маршрут: `api/user/cart`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `200`
  - `JSON`:
    - positions []
      - id
      - shop_position
        - id
        - shop
          - id
          - name
          - open
        - product
          - id
          - name
          - description
          - model
          - category
            - name
          - parameters []
            - parameter_name
              - name
            - value
      - quantity
      - sum
      - product_shops []
        - id
        - name
        - open
        - position
          - id
          - price
          - quantity
    - total_quantity
    - total_sum 
- Результат:
  - Возвращена корзина пользователя, содержащая:
    - список позиций корзины, каждая из которых содержит:
      - позицию магазина с информацией
        - о магазине
        - о товаре
        - о других магазинах, в которых доступен данный товар
      - количество
      - сумму по позиции корзины
    - общее количество по всем позициям корзины
    - общую сумму по всем позициям корзины

### Добавление позиции магазина в корзину пользователя
- Запрос
  - Маршрут: `api/user/cart/`
  - Метод: `POST`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - `JSON`:
    - quantity
    - shop_position (id)
- Ответ:
  - Код: `201`
  - `JSON`:
    - id
    - quantity
    - shop_position
- Результат:
  - Позиция магазина добавлена в корзину пользователя в заданном количестве

### Удаление позиции корзины пользователя
- Запрос
  - Маршрут: `api/user/cart/<cart_position_id>`
  - Метод: `DELETE`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `204`
- Результат:
  - Удалена указанная позиция корзины пользователя

### Обновление позиции корзины пользователя
- Запрос
  - Маршрут: `api/user/cart/<cart_postion_id>/`
  - Метод: `PATCH`
  - Заголовки:
    - Authorization: Token {user_token}
  - `JSON`:
    - quantity
    - shop_position
- Ответ:
  - Код: `200`
  - `JSON`:
    - id
    - quantity
    - shop_position
- Результат:
  - Если обновляется количество, то произведена проверка имеется ли в позиции магазина новое количество
  - Обновлена позиция корзины

### Получение списка получателей прошлых заказов пользователя
- Запрос
  - Маршрут: `api/user/recipients`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `200`
  - `JSON []`:
    - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment

### Создание заказа из позиций корзины пользователя
- Обязательные условия:
  - корзина пользователя не пуста
  - все позиции корзины пользователя доступны к заказу в магазинах в заданном количестве
- Запрос
  - Маршрут: `api/user/orders/`
  - Метод: `POST`
  - Заголовки:
    - Authorization: Token {user_token}
  - `JSON`:
    - recipient
      - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment
- Ответ:
  - Код: `201`
  - `JSON`:
    - id
    - created_at
    - delivired_at
    - status
    - positions []
      - id
      - shop_position
        - id
        - shop
          - id
          - name
          - open
        - product
          - id
          - name
          - description
          - model
          - category
            - name
          - parameters []
            - parameter_name
              - name
            - value 
      - quantity
      - sum
    - recipient
      - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment
    - total_quantity
    - total_sum
- Результат:
  - создан заказ с:
    - позициями заказа
      - каждая позиция заказа перед созданием проверена на наличие в магазине
      - из позиции магазина вычтено количество позиции заказа
    - получателем и его адресом
  - отправлено уведомление на email о создании заказа
    - пользователю
    - всем административным пользователям

### Получение списка заказов пользователя
- Запрос
  - Маршрут: `api/user/orders`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - Параметры (необязательные):
    - status (фильтрация по статусу)
    - created_at (фильтрация по дате и времении создания)
- Ответ:
  - Код: `200`
  - `JSON []`:
    - id
    - created_at
    - delivired_at
    - status
    - positions []
      - id
      - shop_position
        - id
        - shop
          - id
          - name
          - open
        - product
          - id
          - name
          - description
          - model
          - category
            - name
          - parameters []
            - parameter_name
              - name
            - value 
      - quantity
      - sum
    - recipient
      - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment
    - total_quantity
    - total_sum

### Получение заказа пользователя по id
- Запрос
  - Маршрут: `api/user/orders/<order_id>`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `200`
  - `JSON`:
    - id
    - created_at
    - delivired_at
    - status
    - positions []
      - id
      - shop_position
        - id
        - shop
          - id
          - name
          - open
        - product
          - id
          - name
          - description
          - model
          - category
            - name
          - parameters []
            - parameter_name
              - name
            - value 
      - quantity
      - sum
    - recipient
      - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment
    - total_quantity
    - total_sum

### Получение списка магазинов, представителем которых является пользователь
- Запрос
  - Маршрут: `api/user/shops`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
- Ответ:
  - Код: `200`
  - `JSON []`:
    - id
    - name
    - open


### Изменение магазина его представителем
- Обязательные условия
  - пользователь является представителем данного магазина
- Запрос
  - Маршрут: `api/user/shops/<shop_id>/`
  - Метод: `PATCH`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - `JSON`:
    - open
- Ответ:
  - Код: `200`
  - `JSON`:
    - id
    - name
    - open

### Получение списка заказов магазинов, представителем которых является пользователь
- Запрос
  - Маршрут: `api/user/shops/orders`
  - Метод: `GET`
  - Заголовки:
    - `Authorization: Token {user_token}`
  - Параметры (необязательные):
    - status (фильтрация по статусу)
    - created_at (фильтрация по дате и времении создания)
- Ответ:
  - Код: `200`
  - `JSON []`:
    - id
    - created_at
    - delivired_at
    - status
    - positions []
      - id
      - shop_position
        - id
        - shop
          - id
          - name
          - open
        - product
          - id
          - name
          - description
          - model
          - category
            - name
          - parameters []
            - parameter_name
              - name
            - value 
      - quantity
      - sum
    - recipient
      - first_name
      - last_name
      - patronymic
      - email
      - phone
      - address
        - city
        - street
        - house_number
        - house_block
        - house_building
        - appartment
- Результат:
  - возвращён список заказов в которых:
    - присутствуют позиции магазинов, представителем которых является пользователь
    - скрыты остальные позиции заказа


- Запрос
  - Маршрут: `api/`
  - Метод: ``
  - Заголовки:
    - `Authorization: Token {user_token}`
  - `JSON`:
    - 
- Ответ:
  - Код: ``
  - `JSON`:
    - 
- Результат:
  - 