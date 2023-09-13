class HttpResponseNotOk(Exception):
    """Http ответ не 200."""

    pass


class ConnectionError(Exception):
    """Ошибка подключения."""

    pass
