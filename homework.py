import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (NotForSend, TelegramError,
                        WrongResponseCode, DictionaryOrListError)

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
    """Проверяем наличие всех токенов. В случае отсутсвия останавливаем бот."""
    logging.info('Проверка наличия всех токенов')
    env_vars = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_vars = [var for var, value in env_vars.items() if not value]
    if missing_vars:
        logging.critical(
            f'Требуемые переменные окружения отсутствуют: '
            f'{", ".join(missing_vars)}'
        )
    else:
        return True


def send_message(bot, message):
    """Отправляет сообщение в телеграмм."""
    logging.debug('Попытка отправки сообщения')
    try:
        logging.debug('Сообщение отправлено')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error('Сбой при отправке сообщения')
        raise TelegramError(
            f'Ошибка отправки сообщения в telegram: {error}'
        )
    else:
        logging.info('Статус отправлен в телеграм')


def get_api_answer(timestamp):
    """Отправляем запрос к API, получаем статус работы и страницы."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_status = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": params,
    }
    message = ('Начало запроса к API. Запрос: {url}, {headers}, {params}.'
               ).format(**homework_status)
    logging.info(message)
    try:
        response = requests.get(**homework_status)
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
        return response.json()
    except Exception as error:
        message = ('API не возвращает 200. Запрос: {url}, {headers}, {params}.'
                   ).format(**homework_status)
        raise WrongResponseCode(message, error)


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    logging.info('Проверка ответа API на корректность')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if response.get('homeworks') is None:
        message_api = 'Ошибка в ключе homeworks'
        logging.error(message_api)
        raise DictionaryOrListError(message_api)
    if not isinstance(response['homeworks'], list):
        raise TypeError('Проверьте тип данных')
    if not response['homeworks']:
        return {}
    return response['homeworks'][0]


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает подготовленную строку."""
    logging.info('Проверяем статус работы')
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа homework_name в ответе API')
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    if homework_name is None or homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует токен'
        logging.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    start_message = 'Запуск бота'
    send_message(bot, start_message)
    logging.info(start_message)
    prev_msg = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get(
                'current_date', int(time.time())
            )
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks)
            else:
                message = 'Нет новых статусов'
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
            else:
                logging.info(message)
        except NotForSend as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(
                os.path.abspath('main.log'), mode='a', encoding='UTF-8'),
            logging.StreamHandler(stream=sys.stdout)],
        format='%(asctime)s, %(levelname)s, %(funcName)s, '
               '%(lineno)s, %(name)s, %(message)s'
    )
    main()
