import discord
from discord import Embed, Color, TextChannel, Message, ApplicationContext, option, Role, User, Status, \
    AutocompleteContext, OptionChoice, Guild, Member
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup
from discord.ui import InputText, Modal, View
from discord.ext.commands.errors import GuildNotFound

import json
from typing import Union
from random import randint
from datetime import datetime, date, timedelta

from main import db, get_parameter, time_now, MyBot, in_database, string_to_time
from custom_views import DeleteShopItemView


class ModerationCog(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_
        self.shop_items = None

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'ModerationCog' has been loaded"
        self.bot.log_action(txt=log_msg)

    """
    warn 
    - timeout
    tempmute
    mute
    - kick
    tempban
    - ban
    
    logs see (show user records)
    logs clear
    
    - lock
    - unlock
    - lockdown
    """

    @commands.slash_command(name="timeout")
    @option(name="user", description="The user you want to timeout", type=Member)
    @option(name="duration", description="The time for which the user will stay timeout")
    @option(name="reason", description="The reason why you want to timeout that user")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx: ApplicationContext, user: Member, duration: str, reason: str):

        timeout_time = string_to_time(duration)

        author = ctx.author

        await user.timeout_for(duration=timedelta(seconds=timeout_time), reason=reason)

        await ctx.respond(f"{user.mention} has been timeout !", ephemeral=True)
        self.bot.log_action(txt=f"{author} ({author.id}) has timeout {user} ({user.id}) from {ctx.guild_id}")

        # todo: add to user record

        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has timeout {user.mention} for '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Timeout")
        log_emb.set_footer(text=f"Moderation     TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="kick")
    @option(name="user", description="The user you want to kick", type=Member)
    @option(name="reason", description="The reason why you want to kick that user")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: ApplicationContext, user: Member, reason: str):
        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        author = ctx.author

        # todo: add to user record

        await user.kick(reason=reason)

        await ctx.respond(f"{user.mention} has been kicked !", ephemeral=True)
        self.bot.log_action(txt=f"{author} ({author.id}) has banned {user} ({user.id}) from {ctx.guild_id}")

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has kicked {user.mention} for '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Kick")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="ban")
    @option(name="user", description="The user you want to ban", type=Member)
    @option(name="reason", description="The reason why you want to ban that user")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: ApplicationContext, user: Member, reason: str):
        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        author = ctx.author

        # todo: add to user record

        await user.ban(reason=reason)

        await ctx.respond(f"{user.mention} has been banned !", ephemeral=True)
        self.bot.log_action(txt=f"{author} ({author.id}) has banned {user} ({user.id}) from {ctx.guild_id}")

        log_emb = Embed(color=Color.teal(),
                        description=f"{author.mention} has banned {user.mention} for '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Ban")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="lock")
    @option(name="channel", description="The channel you want to lock", required=False)
    @commands.has_permissions(manage_channels=True)
    async def lock_channel(self, ctx: ApplicationContext, channel: TextChannel = None):

        if channel is None:
            channel = ctx.channel

        default_role = ctx.guild.default_role
        default_perms = channel.overwrites_for(default_role)
        default_perms.send_messages = False
        await channel.set_permissions(target=default_role, overwrite=default_perms)

        emb = Embed(color=Color.red(), description=f":lock: <#{channel.id}> has been locked !")
        await ctx.respond(embed=emb)
        self.bot.log_action(txt=f"{ctx.author} ({ctx.author.id}) has locked channel {channel} ({channel.id}) from {ctx.guild_id}")

    @commands.slash_command(name="unlock")
    @option(name="channel", description="The channel you want to unlock", required=False)
    @commands.has_permissions(manage_channels=True)
    async def unlock_channel(self, ctx: ApplicationContext, channel: TextChannel = None):

        if channel is None:
            channel = ctx.channel

        default_role = ctx.guild.default_role
        default_perms = channel.overwrites_for(default_role)
        default_perms.send_messages = True
        await channel.set_permissions(target=default_role, overwrite=default_perms)

        emb = Embed(color=Color.green(), description=f":unlock: <#{channel.id}> has been unlocked !")
        await ctx.respond(embed=emb)
        self.bot.log_action(txt=f"{ctx.author} ({ctx.author.id}) has unlocked channel {channel} ({channel.id}) from {ctx.guild_id}")

    @commands.slash_command(name="lockdown")
    @commands.has_permissions(administrator=True)
    async def lockdown(self, ctx: ApplicationContext):
        guild = ctx.guild
        default_role = guild.default_role

        await ctx.defer()

        for channel in guild.channels:
            perms = channel.overwrites_for(default_role)
            perms.send_messages = False
            perms.send_messages_in_threads = False
            await channel.set_permissions(target=default_role, overwrite=perms)

        emb = Embed(color=Color.red(), description=f":stop_sign: The server has been put under lockdown.")
        await ctx.respond(embed=emb)
        self.bot.log_action(txt=f"{ctx.author} ({ctx.author.id}) has put guild {ctx.guild_id} under lockdown")


def setup(bot_):
    bot_.add_cog(ModerationCog(bot_))
