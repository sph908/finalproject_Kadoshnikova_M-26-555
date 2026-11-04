class ValutatradeError(Exception):
    """
    Общий предок всех ошибок приложения
    """


class InsufficientFundsError(ValutatradeError):
    """
    На кошельке не хватает средств для операции
    """

    def __init__(self, code: str, available: float, required: float) -> None:
        """
        Запоминает валюту, доступный остаток и запрошенную сумму
        """
        super().__init__(
            f"Недостаточно средств: доступно {available:,.4f} {code}, "
            f"требуется {required:,.4f} {code}"
        )
        self.code = code
        self.available = available
        self.required = required


class CurrencyNotFoundError(ValutatradeError):
    """
    Валюта с таким кодом не поддерживается
    """

    def __init__(self, code: str) -> None:
        """
        Запоминает код, который не удалось распознать
        """
        super().__init__(f"Неизвестная валюта '{code}'")
        self.code = code


class ApiRequestError(ValutatradeError):
    """
    Не удалось получить данные от внешнего сервиса курсов
    """

    def __init__(self, reason: str) -> None:
        """
        Запоминает причину сбоя для сообщения пользователю
        """
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
        self.reason = reason
