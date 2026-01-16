# Chudartz
This is the project repo for the [ChudartZ](https://chudartz.com) & [ChudartZ Collectibles](https://chudartz-collectibles.com) websites.


## Developing

```sh
docker compose -f docker-compose.dev.yml up --build
```
You will get errors, this is normal since you need to run migrations.
Keep the docker compose running, and switch to a new terminal.

Now run:
```sh
docker exec -it chudartz-web-1 python manage.py migrate
```
Note: You only need to do this in the initial setup.

You also need to run:
```sh
docker exec -it chudartz-web-1 python manage.py collectstatic
```
Every time you have changed some static files.


Exposes page on [127.0.0.1:81](http://127.0.0.1:81/)
Switch between pokemon en darts via middleware.py