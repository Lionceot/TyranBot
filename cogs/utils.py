from discord import Embed, Color, ApplicationContext, Forbidden
from discord.ext import commands

import json

from main import get_parameter, MyBot, db
from custom_errors import CodeLimitReached, UnknownCode, UnexpectedError


curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)


class Utils(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'UtilsCog' has been loaded"
        self.bot.log_action(txt=log_msg)


def setup(bot_):
    bot_.add_cog(Utils(bot_))
