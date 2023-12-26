FROM python:3.10.12

WORKDIR /usr/src/app

COPY ./orders .
RUN pip install -r requirements.txt
CMD python manage.py makemigrations api; \
    python manage.py migrate; \
    python manage.py collectstatic --noinput; \
    gunicorn orders.wsgi -b 0.0.0.0:80