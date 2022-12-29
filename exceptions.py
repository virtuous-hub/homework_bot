class WrongResponseCode(Exception):
    """Неверный ответ API"""
    pass


class NotForSend(Exception):
    """Исключение не для пересылки в telegram"""
    pass


class DictionaryOrListError(KeyError):
    pass


class TelegramError(NotForSend):
    """Ошибка отправки сообщения в telegram"""
    pass

