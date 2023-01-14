from discord import User
from discord.ext.commands.errors import CommandError


class NotEnoughMoney(CommandError):
    def __init__(self, required_amt: int = None, user_amt: int = None, user_lang: str = None):
        self.required_amt = required_amt
        self.user_amt = user_amt
        self.user_lang = user_lang


class IncorrectBetValue(CommandError):
    def __init__(self, bet_value: int = None):
        self.bet_value = bet_value


class UnknownSign(CommandError):
    pass


class UserIsBot(CommandError):
    def __init__(self, user: User = None):
        self.user = user


class UnknownObject(CommandError):
    pass


class MaxAmountReached(CommandError):
    pass
