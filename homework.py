import http
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HttpResponseNotOk


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверка обязательных переменных.
    При пустом значении переменных будет вызвано исключение.
    """
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        message = 'check_tokens. Отутсвует переменная окружения .env'
        logging.critical(message)
        sys.exit(message)


def send_message(bot, message):
    """Отправка сообщения TELEGRAM_CHAT_ID."""
    logging.debug(f'send_message. Сообщение готово к отправке: {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError:
        logging.exception(f'send_message. Сообщение не отправлено: {message}.')
    else:
        logging.debug(f'send_message. Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """
    Запрос к эндпоинту.
    Если в ответе ошибка, то функция вернёт пустой словарь,
    в следующей итерации повторим запрос.
    """
    logging.debug('get_api_answer. Начинаем запрос к API.'
                  f'timestamp: {timestamp}')
    payload = {'from_date': timestamp}
    message = ('get_api_answer. API не отдаёт данные\n'
               f'Request info ENDPOINT: {ENDPOINT}, HEADERS: {HEADERS},'
               f'payload: {payload}.')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise ConnectionError(message + f'Error: {error}')
    if response.status_code != http.HTTPStatus.OK:
        raise HttpResponseNotOk(message +
                                + f'Response.headers:{response.headers}, '
                                f'Response.status_code:{response.status_code},'
                                f'Response.text:{response.text}'
                                )
    return response.json()


def check_response(response):
    """
    Проверяет результат выполнения get_api_answer().
    Если response {}, сайт не ответил, исключения не будет.
    Если в ответе сайта нет 'current_date' будет вызвано исключение.
    """
    message = 'check_response. Некорректный response'
    if not isinstance(response, dict):
        raise TypeError(message)
    if not response.get('homeworks'):
        raise KeyError(message)
    if not response.get('current_date'):
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(message)


def parse_status(homework):
    """Парсим status ответа по словарю."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError(f'parse_status. В ответе API домашки {homework} '
                       'нет ключа `homework_name`')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise KeyError(f'parse_status. Неожиданный статус {status} домашней '
                       f'работы {homework_name}, обнаруженный в ответе API')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message_last = ''
    message_error_last = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            status_hw_current = response.get('homeworks')[0]
            message = parse_status(status_hw_current)
            if message != message_last:
                send_message(bot, message)
                message_last = message
            else:
                logging.debug('Нет новых статусов')
            timestamp = response.get('current_date')

        except Exception as error:
            message_error = f'Сбой в работе программы: {error}'
            logging.exception(message_error)
            if message_error != message_error_last:
                send_message(bot, message_error)
                message_error_last = message_error
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
