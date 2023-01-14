from dotenv import load_dotenv
from os import listdir, getenv
from logtail import LogtailHandler
import logging
import asyncio

import json
import mysql.connector
from pytz import timezone
from datetime import datetime

import discord
from discord import Embed, Color, Member, Intents, Activity, ActivityType, ApplicationContext, DiscordException, Guild
from discord.ext import commands
from discord.ext.commands import errors, Context

from custom_errors import NotEnoughMoney, UserIsBot, UnknownObject, MaxAmountReached, IncorrectBetValue


load_dotenv()

db = mysql.connector.connect(
    host=getenv("DB_HOST"),
    user=getenv("DB_USER"),
    passwd=getenv("DB_PASSWORD"),
    database=getenv("DB_NAME")
    )

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)
curD = db.cursor(buffered=True)


def in_database(user):
    curA.execute(f"SELECT discordID FROM Users WHERE discordID = {user.id}")
    for x in curA:
        id_found = x[0]
        if id_found == user.id:
            return True
    return False


async def new_player(user):
    exist = in_database(user)
    if not exist:
        now = int(time_now().timestamp())
        curA.execute(f"INSERT INTO users (discordID, coins, language, created) VALUES ({user.id}, 100, 'fr', {now})")
        curB.execute(f"INSERT INTO dailyrecord (discordID, streak, ready, nbDaily, claimed) VALUES ({user.id}, 0, 1, 0, 0)")
        curC.execute(f"INSERT INTO stats (discordID) VALUES ({user.id})")
        curD.execute(f"INSERT INTO potato (discordID) VALUES ({user.id})")
        db.commit()


def time_now():
    return datetime.now(tz=timezone("Europe/Paris"))


def get_parameter(arg: str):
    with open("json/config.json", 'r', encoding='utf-8') as config_file:
        config_values = json.load(config_file)

    try:
        return config_values[arg]
    except KeyError:
        return "KeyError"


def get_text(reference: str, lang: str):
    # TODO : make it open the corresponding file and return the associated text (return reference if error)
    #   if lang == "", open english file
    return reference


def key_with_lowest_value(dico: dict):
    min_value = None
    min_key = None
    for item in dico.items():
        try:
            if item[1] < min_value:
                min_value = item[1]
                min_key = item[0]

        except TypeError:
            min_value = item[1]
            min_key = item[0]
    return min_key


def sort_dict_by_value(d, reverse=False):
    return dict(sorted(d.items(), key=lambda x: x[1], reverse=reverse))


class MyBot(commands.Bot):
    def __init__(self):
        intents = Intents.default()

        with open("json/config.json", "r", encoding="utf-8") as config_file:
            config = json.load(config_file)

        super().__init__(
            command_prefix=commands.when_mentioned_or(config['prefix']),
            intents=intents,
            owner_ids=config['owners'],
            debug_servers=config['debug_server_list'],
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                users=True,
                roles=False,
                replied_user=True
            ),
            slash_commands=True,
            activity=Activity(name="Starting ..."),
            status=discord.Status.idle
        )

        self.ignored_errors = [errors.CommandNotFound, errors.NoPrivateMessage, TimeoutError, asyncio.TimeoutError]

        self.log_file_name = time_now().strftime('%d-%m-%Y_%H.%M.%S')

        logging.basicConfig(filename=f"logs/{self.log_file_name}.log", level=20)
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)

        self.logger = logging.getLogger(__name__)
        self.logger.handlers = [LogtailHandler(source_token=getenv("LOGTAIL_TOKEN"))]

        for filename in listdir('./cogs'):
            if filename.endswith('.py'):
                self.load_extension(f"cogs.{filename[:-3]}")

    def log_action(self, txt: str, level: int = 20):
        self.logger.log(msg=txt, level=level)
        color_code = {
            20: "\033[0;34m",
            30: "\033[0;33m",
            40: "\033[7m\033[1;31m",
            50: "\033[7m\033[1;31m"
        }
        if level in color_code:
            txt = color_code[level] + txt + "\033[0m"
        print(txt)

    async def on_ready(self):
        start_msg = f"[BOT] Bot connected as {self.user}"
        self.log_action(txt=start_msg)

        # await self.change_presence(activity=discord.Game(name="distribuer les cartes"), status=Status.dnd)

        # print("-----------------------")
        # for guild in self.guilds:
        #     print(f"{guild.name} [id: {guild.id}, owner: {guild.owner}|{guild.owner_id}]")
        # print("-----------------------")

        # guild = self.get_guild(925802591894507541)
        # await guild.leave()

    async def on_guild_join(self, guild: Guild):
        text = f"Guild {guild.name} joined. [id: {guild.id}, owner: {guild.owner}|{guild.owner_id}]"
        self.log_action(text)

    async def on_application_command_completion(self, ctx: ApplicationContext):
        args = " ".join([f"[{option['name']}:{option['value']}]" for option in
                         ctx.selected_options]) if ctx.selected_options is not None else ''
        log_msg = f"{ctx.author} ({ctx.author.id}) used app_command '{ctx.command}' {args}"
        self.log_action(txt=log_msg, level=25)

    # TODO: handle cooldown errors (not in application commands)
    async def on_command_error(self, ctx: Context, exception: errors.CommandError):
        if exception in self.ignored_errors:
            pass

        elif isinstance(exception, errors.NotOwner):
            emb = Embed(color=Color.red(), description="You are not my owner")
            await ctx.reply(embed=emb, delete_after=5)

        elif isinstance(exception, errors.RoleNotFound):
            pass

        elif isinstance(exception, errors.UserNotFound):
            pass

        elif isinstance(exception, errors.MissingRequiredArgument):
            emb = Embed(color=Color.red(), description=f"{ctx.command.brief}")
            emb.set_author(name="Please respect the following syntax :")
            await ctx.reply(embed=emb)

        elif isinstance(exception, NotEnoughMoney):
            emb = Embed(color=Color.red(), description="You don't have enough money to do that")
            await ctx.reply(embed=emb)

        elif isinstance(exception, UserIsBot):
            emb = Embed(color=Color.red(), description="Bots can't interact with the economy")
            await ctx.reply(embed=emb)

        else:
            self.log_action(txt=f"Unhandled error occurred ({type(exception)})", level=50)

    async def on_application_command_error(self, ctx: ApplicationContext, exception: errors.CommandError):
        if exception in self.ignored_errors:
            return

        user = ctx.user
        await new_player(user)
        curA.execute(f"SELECT language FROM users WHERE discordID = {user.id}")
        user_lang = curA.fetchone()[0]

        if isinstance(exception, errors.NotOwner):
            emb = Embed(color=Color.red(), description=get_text("command.owner_only", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, NotEnoughMoney):
            emb = Embed(color=Color.red(), description=get_text("command.not_enough_money", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, UserIsBot):
            emb = Embed(color=Color.red(), description=get_text("command.user_is_bot", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, UnknownObject):
            emb = Embed(color=Color.red(), description=get_text("command.unknown_object", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, MaxAmountReached):
            emb = Embed(color=Color.red(), description=get_text("buy.max_amount", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, IncorrectBetValue):
            emb = Embed(color=Color.red(), description=get_text("command.incorrect_bet", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        elif isinstance(exception, errors.CommandOnCooldown):
            # todo: add time formatting for cooldown value
            emb = Embed(color=Color.red(), description=get_text("command.on_cooldown", user_lang))
            await ctx.respond(embed=emb, ephemeral=True)

        else:
            self.log_action(txt=f"Unhandled error occurred ({type(exception)}) : {exception}", level=50)


bot = MyBot()


@bot.slash_command(name="ping")
async def ping(ctx: ApplicationContext):
    latency = round(bot.latency * 1000)
    await ctx.respond(f"🏓 Pong! ({latency}ms)", ephemeral=True)

    limit = get_parameter('ping_limit')

    if latency > limit:
        bot.log_action(txt=f"Bot ping is at {latency} ms", level=30)


@bot.slash_command(name="reload", description="Redémarre une cog", brief="Reload a cog", hidden=True, guild_ids=[733722460771581982])
@commands.is_owner()
async def reload(ctx: ApplicationContext, extension=None):
    if not extension:
        for filename_ in listdir('./cogs'):
            if filename_.endswith('.py'):
                try:
                    bot.reload_extension(f"cogs.{filename_[:-3]}")
                    await ctx.respond(f"> Cog `{filename_[:-3]}` successfully reloaded", ephemeral=True)

                except discord.ExtensionNotLoaded:
                    bot.load_extension(f"cogs.{filename_[:-3]}")
                    await ctx.respond(f"> Cog `{filename_[:-3]}` successfully loaded", ephemeral=True)

    else:
        try:
            bot.reload_extension(f"cogs.{extension}")
            await ctx.respond(f"> Cog `{extension}` successfully reloaded", ephemeral=True)

        except discord.ExtensionNotLoaded:
            try:
                bot.load_extension(f"cogs.{extension}")
                await ctx.respond(f"> Cog `{extension}` successfully loaded", ephemeral=True)

            except discord.ExtensionNotFound:
                await ctx.respond(f"> Cog `{extension}` not found", ephemeral=True)


@bot.slash_command(name="load", description="Charge une cog", brief="Load a cog", hidden=True, guild_ids=[733722460771581982])
@commands.is_owner()
async def load(ctx: ApplicationContext, extension=None):
    try:
        bot.load_extension(f"cogs.{extension}")
        await ctx.respond(f"> Cog `{extension}` successfully loaded", ephemeral=True)

    except discord.ExtensionNotFound:
        await ctx.respond(f"> Cog `{extension}` not found", ephemeral=True)

    except discord.ExtensionAlreadyLoaded:
        await ctx.respond(f"> Cog `{extension}` already loaded", ephemeral=True)


@bot.slash_command(name="unload", description="Décharge une cog", brief="Unload a cog", hidden=True, guild_ids=[733722460771581982])
@commands.is_owner()
async def unload(ctx: ApplicationContext, extension=None):
    try:
        bot.unload_extension(f"cogs.{extension}")
        await ctx.respond(f"> Cog `{extension}` successfully unloaded", ephemeral=True)

    except discord.ExtensionNotLoaded:
        await ctx.respond(f"> Cog `{extension}` not loaded", ephemeral=True)

    except discord.ExtensionNotFound:
        await ctx.respond(f"> Cog `{extension}` not found", ephemeral=True)


if __name__ == '__main__':
    bot.run(getenv("BOT_TOKEN"))
    bot.log_action(txt="[BOT] Bot closed.")
