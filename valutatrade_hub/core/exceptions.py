class ValutatradeError(Exception):
    """
    Общий предок всех ошибок приложения
    """


class UserNotFoundError(ValutatradeError):
    """
    Пользователь с таким именем не зарегистрирован
    """


class InvalidPasswordError(ValutatradeError):
    """
    Введённый пароль не совпадает с сохранённым
    """


class InsufficientFundsError(ValutatradeError):
    """
    На кошельке не хватает средств для операции
    """
