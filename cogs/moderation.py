from discord import Embed, Color, TextChannel, ApplicationContext, option, User, Member
from discord.ext import commands
from discord.commands import SlashCommandGroup

import json
from datetime import timedelta

from main import MyBot
from custom_functions import get_parameter, time_now, string_to_time, time_to_string, add_event, is_disabled_check


class Moderation(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'ModerationCog' has been loaded"
        self.bot.log_action(log_msg, self.bot.bot_logger)

    @commands.slash_command(name="warn")
    @option(name="user", description="The user you want to timeout", type=User)
    @option(name="reason", description="The reason why you want to timeout that user")
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def warn(self, ctx: ApplicationContext, user: User, reason: str):
        await ctx.defer()

        author = ctx.author

        await ctx.respond(f"{user.mention} has been warned !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has warned {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "warn",
            "duration": -1,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        log_emb = Embed(color=Color.teal(),
                        description=f"{author.mention} has warned {user.mention} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Warn")
        log_emb.set_footer(text=f"Moderation     TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

        warn_emb = Embed(color=Color.light_grey(), title=f"{ctx.guild.name} - Warn",
                         description=f"You have been warned on {ctx.guild.name} for {reason}")
        await user.send(embed=warn_emb)

    @commands.slash_command(name="timeout")
    @option(name="user", description="The user you want to timeout", type=Member)
    @option(name="duration", description="The time for which the user will stay timeout")
    @option(name="reason", description="The reason why you want to timeout that user")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def timeout(self, ctx: ApplicationContext, user: Member, duration: str, reason: str):
        await ctx.defer()

        timeout_time = string_to_time(duration)

        author = ctx.author

        await user.timeout_for(duration=timedelta(seconds=timeout_time), reason=reason)

        await ctx.respond(f"{user.mention} has been timeout !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has timeout {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "timeout",
            "duration": timeout_time,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has timeout {user.mention} for `{duration}` because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Timeout")
        log_emb.set_footer(text=f"Moderation     TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="tempmute")
    @option(name="user", description="The user you want to mute", type=Member)
    @option(name="duration", description="The time for which the user will stay muted")
    @option(name="reason", description="The reason why you want to mute that user")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def tempmute(self, ctx: ApplicationContext, user: Member, duration: str, reason: str):
        await ctx.defer()

        mute_time = string_to_time(duration)

        log_channel_id, bot_version, mute_role_id = get_parameter(["moderation_logs", "version", "mute_role"])

        guild = ctx.guild
        author = ctx.author
        log_channel = self.bot.get_channel(log_channel_id)

        # Create a new mute role if none if configured
        if mute_role_id is None:
            default_perms = guild.default_role.permissions
            default_perms.send_messages = False
            mute_role = await guild.create_role(name="muted", reason="No mute role configured",
                                                permissions=default_perms)

            with open("json/config.json", "r", encoding="utf-8") as config_file:
                config = json.load(config_file)

            config['mute_role'] = mute_role.id

            with open("json/config.json", "w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2)

            self.bot.log_action(f"New mute role ({mute_role.id}) in configuration for guild '{guild.id}'", self.bot.mod_logger)

        else:
            mute_role = guild.get_role(mute_role_id)

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
                "type": "tempmute",
                "duration": mute_time,
                "reason": reason,
                "author": author.id,
                "date": round(time_now().timestamp())
            }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        # Add to events
        end_timestamp = round(time_now().timestamp()) + mute_time

        new_event = {
            "type": "tempmute",
            "user": user.id,
            "guild": guild.id
        }

        add_event(end_timestamp, new_event)

        await user.add_roles(mute_role)

        await ctx.respond(f"{user.mention} has been muted for {duration} !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has muted {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has muted {user.mention} for {duration} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Mute")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="mute")
    @option(name="user", description="The user you want to mute", type=Member)
    @option(name="reason", description="The reason why you want to mute that user")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def mute(self, ctx: ApplicationContext, user: Member, reason: str):
        await ctx.defer()
        log_channel_id, bot_version, mute_role_id = get_parameter(["moderation_logs", "version", "mute_role"])

        guild = ctx.guild
        author = ctx.author
        log_channel = self.bot.get_channel(log_channel_id)

        # Create a new mute role if none if configured
        if mute_role_id is None:
            default_perms = guild.default_role.permissions
            default_perms.send_messages = False
            mute_role = await guild.create_role(name="muted", reason="No mute role configured", permissions=default_perms)

            with open("json/config.json", "r", encoding="utf-8") as config_file:
                config = json.load(config_file)

            config['mute_role'] = mute_role.id

            with open("json/config.json", "w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2)

            self.bot.log_action(f"New mute role ({mute_role.id}) in configuration for guild '{guild.id}'", self.bot.mod_logger)

        else:
            mute_role = guild.get_role(mute_role_id)

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "mute",
            "duration": -1,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        await user.add_roles(mute_role)

        await ctx.respond(f"{user.mention} has been muted !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has muted {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has muted {user.mention} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Mute")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="kick")
    @option(name="user", description="The user you want to kick", type=Member)
    @option(name="reason", description="The reason why you want to kick that user")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def kick(self, ctx: ApplicationContext, user: Member, reason: str):
        await ctx.defer()
        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        author = ctx.author

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "kick",
            "duration": -1,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        await user.kick(reason=reason)

        await ctx.respond(f"{user.mention} has been kicked !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has banned {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        log_emb = Embed(color=Color.teal(), description=f"{author.mention} has kicked {user.mention} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Kick")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="tempban")
    @option(name="user", description="The user you want to ban", type=Member)
    @option(name="duration", description="The time for which the user will stay banned")
    @option(name="reason", description="The reason why you want to ban that user")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def tempban(self, ctx: ApplicationContext, user: Member, duration: str, reason: str):
        await ctx.defer()
        ban_time = string_to_time(duration)

        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        author = ctx.author

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "tempban",
            "duration": ban_time,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

            # Add to events
            end_timestamp = round(time_now().timestamp()) + ban_time

            new_event = {
                "type": "tempban",
                "user": user.id,
                "guild": ctx.guild_id
            }

            add_event(end_timestamp, new_event)

        await user.ban(reason=reason)

        await ctx.respond(f"{user.mention} has been banned !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has banned {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        log_emb = Embed(color=Color.teal(),
                        description=f"{author.mention} has banned {user.mention} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Ban")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    @commands.slash_command(name="ban")
    @option(name="user", description="The user you want to ban", type=Member)
    @option(name="reason", description="The reason why you want to ban that user")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def ban(self, ctx: ApplicationContext, user: Member, reason: str):
        await ctx.defer()
        log_channel_id, bot_version = get_parameter(["moderation_logs", "version"])
        log_channel = self.bot.get_channel(log_channel_id)

        author = ctx.author

        # Add to user record
        with open("json/moderation.json", "r", encoding="utf-8") as mod_file:
            mod_logs = json.load(mod_file)

        new_log = {
            "type": "ban",
            "duration": -1,
            "reason": reason,
            "author": author.id,
            "date": round(time_now().timestamp())
        }

        if str(user.id) in mod_logs:
            mod_logs[str(user.id)].append(new_log)

        else:
            mod_logs[str(user.id)] = [new_log]

        with open("json/moderation.json", "w", encoding="utf-8") as mod_file:
            json.dump(mod_logs, mod_file, indent=2)

        await user.ban(reason=reason)

        await ctx.respond(f"{user.mention} has been banned !", ephemeral=True)
        self.bot.log_action(f"{author} ({author.id}) has banned {user} ({user.id}) from {ctx.guild_id}", self.bot.mod_logger)

        log_emb = Embed(color=Color.teal(),
                        description=f"{author.mention} has banned {user.mention} because '{reason}'")
        log_emb.add_field(name="Details", value=f"• Author id : {author.id} \n• User id : {user.id}")
        log_emb.set_author(name="Moderation log - Ban")
        log_emb.set_footer(text=f"Moderation   -   TyranBot • {bot_version}")

        await log_channel.send(embed=log_emb)

    logs_group = SlashCommandGroup("logs", "Show user moderation logs")

    @logs_group.command(name="see")
    @option(name="user", description="The user whose logs you're looking for")
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def logs_see(self, ctx: ApplicationContext, user: User):
        with open("json/moderation.json", "r", encoding="utf-8") as log_file:
            logs = json.load(log_file)

        cleared = False

        if str(user.id) in logs:
            if len(logs[str(user.id)]) > 0:
                user_log = logs[str(user.id)]
                text = "• " + "\n• ".join(
                    [
                        f"{log['type']} by <@{log['author']}>"
                        f"{' (' + time_to_string(log['duration']) + ')' if log['duration'] != -1 else ''} : "
                        f"{log['reason']}" for log in user_log
                    ]
                )

                emb = Embed(color=Color.teal(), description=f"This user has {len(user_log)} moderation logs.").set_author(name=f"{user} moderation logs")
                emb.add_field(name="Details :", value=text)
                await ctx.respond(embed=emb)
                return

            else:
                cleared = True

        emb = Embed(color=Color.teal(), description=f"This user has no moderation logs. {'(cleared)' if cleared else ''}")
        emb.set_author(name=f"{user} moderation logs")
        await ctx.respond(embed=emb)

    @logs_group.command(name="clear")
    @option(name="user", description="The user whose logs you want to delete")
    @commands.is_owner()
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def logs_clear(self, ctx: ApplicationContext, user: User):
        with open("json/moderation.json", "r", encoding="utf-8") as log_file:
            logs = json.load(log_file)

        if str(user.id) in logs:
            if len(logs[str(user.id)]) > 0:
                logs[str(user.id)] = []
                with open("json/moderation.json", "w", encoding="utf-8") as log_file:
                    json.dump(logs, log_file, indent=2)

                await ctx.respond(f"{user.mention}'s moderation logs were cleared")

            else:
                await ctx.respond(f"{user.mention}'s moderation logs have already been cleared")

        else:
            await ctx.respond(f"{user.mention} doesn't have any record", ephemeral=True)

    @commands.slash_command(name="lock")
    @option(name="channel", description="The channel you want to lock", required=False)
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def lock_channel(self, ctx: ApplicationContext, channel: TextChannel = None):

        if channel is None:
            channel = ctx.channel

        default_role = ctx.guild.default_role
        default_perms = channel.overwrites_for(default_role)
        default_perms.send_messages = False
        await channel.set_permissions(target=default_role, overwrite=default_perms)

        emb = Embed(color=Color.red(), description=f":lock: <#{channel.id}> has been locked !")
        await ctx.respond(embed=emb)
        self.bot.log_action(f"{ctx.author} ({ctx.author.id}) has locked channel {channel} ({channel.id}) from {ctx.guild_id}", self.bot.mod_logger)

    @commands.slash_command(name="unlock")
    @option(name="channel", description="The channel you want to unlock", required=False)
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
    async def unlock_channel(self, ctx: ApplicationContext, channel: TextChannel = None):

        if channel is None:
            channel = ctx.channel

        default_role = ctx.guild.default_role
        default_perms = channel.overwrites_for(default_role)
        default_perms.send_messages = True
        await channel.set_permissions(target=default_role, overwrite=default_perms)

        emb = Embed(color=Color.green(), description=f":unlock: <#{channel.id}> has been unlocked !")
        await ctx.respond(embed=emb)
        self.bot.log_action(f"{ctx.author} ({ctx.author.id}) has unlocked channel {channel} ({channel.id}) from {ctx.guild_id}", self.bot.mod_logger)

    @commands.slash_command(name="lockdown")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.check(is_disabled_check)
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
        self.bot.log_action(f"{ctx.author} ({ctx.author.id}) has put guild {ctx.guild_id} under lockdown", self.bot.mod_logger)


def setup(bot_):
    bot_.add_cog(Moderation(bot_))
