from discord import Embed, Color, TextChannel, ApplicationContext, option, User, Member
from discord.ext import commands
from discord.commands import SlashCommandGroup, UserCommand, MessageCommand, SlashCommand
from discord.ext.commands import Command

import json
from datetime import timedelta

from main import get_parameter, time_now, MyBot, string_to_time, time_to_string


class Help(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'HelpCog' has been loaded"
        self.bot.log_action(txt=log_msg)

    @commands.command(name="help", usage="", description="Give information about commands")
    async def help(self, ctx):
        res = ""
        cogs_to_exclude = ["Admin", "Moderation", "Test", "Help"]
        cogs = [[cog, self.bot.get_cog(cog).get_commands()] for cog in self.bot.cogs if cog not in cogs_to_exclude]

        for cog in cogs:
            res += f"## {cog[0]}\n\n``` \n"
            for cmd in cog[1]:
                if isinstance(cmd, SlashCommandGroup):
                    for s1 in cmd.walk_commands():
                        if isinstance(s1, SlashCommandGroup):
                            for s2 in s1.walk_commands():
                                res += format_command_name(s2, f"{cmd.name} {s1.name}")
                        else:
                            res += format_command_name(s1, cmd.name)

                else:
                    res += format_command_name(cmd)

            res += "```\n"

        emb = Embed(color=Color.dark_orange(),
                    description="`< >` : required argument\n`[ ]` : optional argument\n\n" + res)
        emb.set_author(name="Help menu")
        await ctx.reply(embed=emb)

    @commands.command(name="admin_help", hidden=True)
    @commands.is_owner()
    async def admin_help(self, ctx):
        res = ""
        cogs = [[cog, self.bot.get_cog(cog).get_commands()] for cog in self.bot.cogs]

        for cog in cogs:
            res += f"## {cog[0]}\n\n```"
            for cmd in cog[1]:
                if isinstance(cmd, SlashCommandGroup):
                    for s1 in cmd.walk_commands():
                        if isinstance(s1, SlashCommandGroup):
                            for s2 in s1.walk_commands():
                                res += format_command_name(s2, f"{cmd.name} {s1.name}")
                        else:
                            res += format_command_name(s1, cmd.name)

                else:
                    res += format_command_name(cmd)

            res += "```\n"

        emb = Embed(color=Color.dark_orange(), description=res).set_author(name="Command list")
        await ctx.reply(embed=emb)


def format_command_name(cmd, cog_name: str = None):
    """
    Get a command in input and return a string according to the type of command it is
    """
    if isinstance(cmd, (UserCommand, MessageCommand)):
        return ""

    if isinstance(cmd, SlashCommand):
        prefix = f"\t/"
        suffix = " ".join([f"{f'<{opt.name}>' if opt.required else f'[{opt.name}]'}" for opt in cmd.options])

    elif isinstance(cmd, Command):
        prefix = f"\t{get_parameter('prefix')}"
        suffix = cmd.usage if cmd.usage is not None else "▫"

    else:
        prefix = f"\t‼ "
        suffix = "‼"

    if cog_name is None:
        return f"{prefix}{cmd.name} {suffix}\n"

    return f"{prefix}{cog_name} {cmd.name} {suffix}\n"


def setup(bot_):
    bot_.add_cog(Help(bot_))
