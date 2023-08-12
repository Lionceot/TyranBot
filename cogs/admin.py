import discord
from discord import Embed, Color, TextChannel, Message, ApplicationContext, option, Role, User, Status, \
    AutocompleteContext, OptionChoice, Guild, SlashCommand, File
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.ui import InputText, Modal, View

import json
import os
import tempfile

from main import db, MyBot, in_database
from custom_views import DeleteShopItemView, AdminCodesView
from custom_errors import CommandDisabled
from custom_functions import add_event, get_parameter, var_set, time_now, is_disabled_check, text_to_file


curLang = db.cursor(buffered=True)      # cursor used to get the language setting in all the commands

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)
curD = db.cursor(buffered=True)
curE = db.cursor(buffered=True)
curF = db.cursor(buffered=True)


def get_all_config_var_name():
    with open("config.json", "r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    return list(config.keys())


class Admin(commands.Cog):

    def __init__(self, bot_: MyBot):
        self.bot = bot_
        self.shop_items = None

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'AdminCog' has been loaded"
        self.bot.log_action(log_msg, self.bot.bot_logger)

    admin_group = SlashCommandGroup("admin", "Admin commands")
    shop_sub = admin_group.create_subgroup("shop", "Shop management")
    inv_sub = admin_group.create_subgroup("inv", "Inventory management")
    set_sub = admin_group.create_subgroup("set", "Define several things")
    suggestion_sub = admin_group.create_subgroup("suggestion", "commands related to suggestions management")
    tickets_sub = admin_group.create_subgroup("ticket", "Tickets system management")
    toggle_sub = admin_group.create_subgroup("toggle", "Toggle intern function")
    coins_sub = admin_group.create_subgroup("coins", "Modify coins amounts")
    commands_sub = admin_group.create_subgroup("commands", "Commands management")

    @admin_group.command(name="shutdown")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def shutdown(self, ctx: ApplicationContext):
        self.bot.log_action(f"{ctx.author} stopped the bot", self.bot.bot_logger)
        await ctx.respond("Shutting down the bot !", ephemeral=True)
        await self.bot.close()

    @admin_group.command(name="dreset", description="Redonne la permission de refaire un daily",
                         brief="Give everyone the permission to do a daily")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def forced_daily_reset(self, ctx: ApplicationContext):
        curA.execute("UPDATE dailyrecord SET ready = 1")
        db.commit()
        self.bot.log_action(f"[ECO] Daily bonus available (forced by {ctx.author})", self.bot.eco_logger)
        await ctx.respond(f"Done !", ephemeral=True)

    @admin_group.command(name="guilds")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_guilds(self, ctx: ApplicationContext):
        emb = Embed(color=0x36393F).set_author(name="Guild list")
        for guild in self.bot.guilds:
            emb.add_field(name=f"{guild.name} ({guild.id})", value=f"owner: {guild.owner_id}", inline=False)
        await ctx.respond(embed=emb, ephemeral=True)

    @admin_group.command(name="leave", description="Make the bot leave a specific server", guild_only=True)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_leave(self, ctx: ApplicationContext, guild: Guild):
        await guild.leave()
        self.bot.log_action(f"[ADMIN] {ctx.author} made the bot leave the guild '{guild.name}' ({guild.id})", self.bot.admin_logger)
        await ctx.respond("Bot has been successfully left the guild !", ephemeral=True)

    @staticmethod
    async def user_inventory_autocomplete(ctx: AutocompleteContext):
        user = ctx.options['user']
        object_id = ctx.options['object_id']
        curA.execute(f"SELECT object_id FROM bag WHERE discordID={user.id}, object_id LIKE '%{object_id}%'")
        return [x[0] for x in curA.fetchall()]

    @staticmethod
    async def shop_item_autocomplete(ctx: AutocompleteContext):
        object_id = ctx.options['object_id']
        curA.execute(f"SELECT object_id FROM objects WHERE object_id LIKE '%{object_id}%'")
        return [x[0] for x in curA.fetchall()]

    @inv_sub.command(name="add_item", description="Add an item in someone's inventory", guild_only=True)
    @option(name="user", description="The targeted user")
    @option(name="object_id", description="The unique descriptor of the item you want to add",
            autocomplete=shop_item_autocomplete)
    @option(name="amount", description="How many times you want to add this item in their inventory",
            min_value=1, max_value=100, default=1)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_inv_add_item(self, ctx: ApplicationContext, user: User, object_id: str, amount: int):
        # todo: code this
        await ctx.respond("end of command", ephemeral=True)

    @inv_sub.command(name="remove_item", description="Remove an item from someone's inventory", guild_only=True)
    @option(name="user", description="The targeted user")
    @option(name="object_id", description="The unique descriptor of the item you want to add",
            autocomplete=user_inventory_autocomplete)
    @option(name="amount", description="How many times you want to remove this item from their inventory",
            min_value=1, max_value=100, default=1)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_inv_remove_item(self, ctx: ApplicationContext, user: User, object_id: str, amount: int):
        # todo: code this
        await ctx.respond("end of command", ephemeral=True)

    @coins_sub.command(name="add", description="Add coins to someone's account", guild_only=True)
    @option(name="user")
    @option(name="amount")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_coins_add(self, ctx: ApplicationContext, user: User, amount: int):
        if not in_database(user):
            await ctx.respond("User has never used the economy", ephemeral=True)

        else:
            curA.execute(f"UPDATE users SET coins = coins + {amount} WHERE discordID = {user.id}")
            db.commit()
            self.bot.log_action(f"[ADMIN] {user} has been credited {amount} coins", self.bot.eco_logger)
            await ctx.respond(f"{amount} coins has been added to {user.mention}'s account", ephemeral=True)

    @coins_sub.command(name="remove", description="Remove coins from someone's account", guild_only=True)
    @option(name="user")
    @option(name="amount")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_coins_remove(self, ctx: ApplicationContext, user: User, amount: int):
        if not in_database(user):
            await ctx.respond("User has never used the economy", ephemeral=True)

        else:
            curA.execute(f"UPDATE users SET coins = coins - {amount} WHERE discordID = {user.id}")
            db.commit()
            self.bot.log_action(f"[ADMIN] {user} has been debited {amount} coins", self.bot.eco_logger)
            await ctx.respond(f"{amount} coins has been removed to {user.mention}'s account", ephemeral=True)

    @coins_sub.command(name="set", description="Set the amount of coins of someone", guild_only=True)
    @option(name="user")
    @option(name="amount")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_coins_set(self, ctx: ApplicationContext, user: User, amount: int):
        if not in_database(user):
            await ctx.respond("User has never used the economy", ephemeral=True)

        else:
            curA.execute(f"UPDATE users SET coins = {amount} WHERE discordID = {user.id}")
            db.commit()
            self.bot.log_action(f"[ADMIN] {user} has now {amount} coins", self.bot.eco_logger)
            await ctx.respond(f"{user.mention} now has {amount} coins.", ephemeral=True)

    @set_sub.command(name="bot-status")
    @option(name="status", choices=["online", "offline", "idle", "dnd"])
    @option(name="activity", choices=["playing", "watching", "listening", "streaming"])
    @option(name="text", description="The text after the activity type")
    @option(name="url", description="Url if activity is streaming", required=False)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_set_bot_status(self, ctx, status: str, activity: str, text: str, url: str = None):
        if activity == "streaming" and not url:
            await ctx.respond("give me an url", ephemeral=True)
            return
        dico = {
            "playing": discord.Game(name=text),
            "streaming": discord.Activity(type=discord.ActivityType.streaming, name=text, url=url),
            "listening": discord.Activity(type=discord.ActivityType.listening, name=text),
            "watching": discord.Activity(type=discord.ActivityType.watching, name=text),
            "online": Status.online,
            "offline": Status.offline,
            "idle": Status.idle,
            "dnd": Status.dnd
        }
        await self.bot.change_presence(activity=dico[activity], status=dico[status])
        self.bot.log_action(f"[ADMIN] {ctx.author} changed the bot status to '{activity} {text}{f' {url}' if url is not None else ''}'", self.bot.admin_logger)
        await ctx.respond("Status changed !", ephemeral=True)

    @set_sub.command(name="boost")
    @option(name="value", description="boost's value", type=int)
    @option(name="boost_type", description="What kind of boost is it", choices=["coins"])
    @option(name="target", choices=["everyone", "role", "user"])
    @option(name="length", description="How long the boost last (in seconds)")
    @option(name="role", description="Role being affected", type=Role, required=False)
    @option(name="user", description="User being affected", type=User, required=False)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_set_boost(self, ctx: ApplicationContext, value: int, boost_type: str, target: str, length: int, role: Role = None, user: User = None):
        end = round(time_now().timestamp()) + length

        if target == "everyone":
            var_set('global_coins_boost', value)
            self.bot.log_action(f"[ADMIN] Global boost value has been set to {value} for {length}s", self.bot.eco_logger)
            await ctx.respond(f"Global income boost value has been set to `{value}`", ephemeral=True)

            add_event(end, {
                "type": f"{boost_type}-boost",
                "value": 1
            })

        elif target == "role":
            if not role:
                await ctx.respond("Please specify a role", ephemeral=True)
            else:
                users_id = [member.id for member in role.members]
                users_values = ', '.join([f"({u_id}, {end}, {value}, '{boost_type}')" for u_id in users_id])

                curA.execute(f"INSERT INTO active_boosts (discordID, endTimestamp, multiplier, boostType) VALUES "
                             f"{users_values}")
                db.commit()

                self.bot.log_action(f"[ADMIN] Boost value for role '{role}' has been multiplied by {value} for {length}s", self.bot.eco_logger)
                await ctx.respond(f"Everyone that has {role} has now a boost of {value}!", ephemeral=True)

        elif target == "user":
            if not user:
                await ctx.respond("Please specify a user", ephemeral=True)

            else:
                curA.execute(f"INSERT INTO active_boosts (discordID, endTimestamp, multiplier, boostType) VALUES "
                             f"({user.id}, {end}, {value}, '{boost_type}')")
                db.commit()

                self.bot.log_action(f"[ADMIN] {user}'s boost value has been multiplied by {value} for {length}s", self.bot.eco_logger)
                await ctx.respond("Done !", ephemeral=True)

        else:
            await ctx.respond(f"That's an unexpected behavior please contact {get_parameter('emergency-contact')}",
                              ephemeral=True)
            self.bot.log_action(f"[CMD] Unexpected behavior in '{ctx.command.qualified_name}' raise by {ctx.author}", self.bot.cmd_logger, 40)

    @suggestion_sub.command(name="channel", description="Define a new channel where suggestions will be sent")
    @option(name="channel", description="The channel", type=TextChannel)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_suggestion_channel(self, ctx, channel: TextChannel):
        with open("config.json", 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)

        old_id = config["suggest-channel"]
        config["suggest-channel"] = channel.id
        log_channel = self.bot.get_channel(config["config-update-channel"])

        with open("config.json", "w") as o:
            json.dump(config, o, indent=2)

        log_em = Embed(color=Color.embed_background()).add_field(name="Suggest channel update",
                                                                 value=f"`{old_id}` -> `{channel.id}`")
        log_em.set_footer(text=f"{ctx.author} - {ctx.author.id}")
        await log_channel.send(embed=log_em)

        self.bot.log_action(f"[ADMIN] Suggestion channel has been changed to {channel.id}", self.bot.admin_logger)
        await ctx.respond("\✔️ Channel successfully updated !", ephemeral=True)

    @suggestion_sub.command(name="status", description="Change the status of a suggestion")
    @option(name="message", type=Message)
    @option(name="status", choices=["Refused", "Accepted", "WIP", "Waiting", "Implemented"])
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_suggestion_status(self, ctx, message: Message, status: str):
        status_color = {"Refused": 0xea8357, "Accepted": 0x7cd444, "WIP": 0xe0ab48,
                        "Implemented": 0x065535, "Waiting": 0x9999ff}

        if status not in status_color:
            await ctx.respond(f"Invalid status, please contact {get_parameter('emergency-contact')}", delete_after=3)
            return

        if len(message.embeds) != 1:
            await ctx.respond("Incorrect message", delete_after=3)
            return

        embed = message.embeds[0]
        new_emb = Embed(color=status_color[status], title=embed.title, description=embed.description)
        new_emb.add_field(name="État de la suggestion", value=status)
        new_emb.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
        await message.edit(embed=new_emb)

        self.bot.log_action(f"[ADMIN] Suggestion '{message.id}' is now '{status}'", self.bot.admin_logger)
        await ctx.respond(f"Suggestion status updated to {status}", ephemeral=True)

    @suggestion_sub.command(name="setup", description="Owner only")
    @option(name="channel", description="Channel where it's sent", type=TextChannel, required=False)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_suggest_setup(self, ctx, channel: TextChannel = None):
        channel_id = channel.id if channel else ctx.channel.id
        new_channel = self.bot.get_channel(channel_id)

        with open("config.json", 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            version = config["version"]
            old_ids = config["suggest-message-id"]
            suggest_channel_id = config["suggest-channel"]
        with open("messages/suggest.txt", 'r', encoding='utf-8') as content:
            F = content.read()

        suggest_channel = self.bot.get_channel(suggest_channel_id)

        class SuggestModal(Modal):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.add_item(InputText(
                    label="Titre de votre suggestion",
                    placeholder="Un titre explicite représentant votre suggestion",
                    style=discord.InputTextStyle.short
                ))

                self.add_item(
                    InputText(
                        label="Description de votre suggestion",
                        placeholder="Décrivez votre proposition le plus précisément possible",
                        style=discord.InputTextStyle.long,
                    )
                )

            async def callback(self, interaction: discord.Interaction):
                sug_embed = Embed(color=0x9999FF, title=self.children[0].value, description=self.children[1].value)
                sug_embed.add_field(name="État de la suggestion", value="Waiting")
                message = await suggest_channel.send(embed=sug_embed)
                url = interaction.user.default_avatar.url if not interaction.user.avatar else interaction.user.avatar.url
                sug_embed.set_footer(
                    text=f"Suggestion de {interaction.user.name}#{interaction.user.discriminator} - {message.id}",
                    icon_url=url)
                await message.edit(embed=sug_embed)
                await message.add_reaction("<:upvote:980121414990454814>")
                await message.add_reaction("<:downvote:980121415019814972>")
                await interaction.response.send_message(
                    f"Merci de votre suggestion ! retrouvez la dans <#{config['suggest-channel']}> pour voir si elle sera acceptée ou non !",
                    ephemeral=True)

        class SuggestionView(View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="Faire une suggestion", style=discord.ButtonStyle.green)
            async def button_callback(self, button, interaction):
                modal = SuggestModal(title="Formulaire de suggestion")
                await interaction.response.send_modal(modal)

        rulesEmb = Embed(color=Color.dark_teal(), description=F)
        messageEmb = Embed(color=Color.teal(),
                           description="Pour faire une suggestion, cliquez sur le bouton ci-dessous. \nVous êtes responsable des suggestions faites depuis votre compte.")
        messageEmb.set_author(name="Suggestions")
        messageEmb.set_footer(text=f"『Suggestions』     『 TyranBot 』•『v{version}』")

        for message_id in old_ids[1]:
            await self.bot.http.delete_message(old_ids[0], message_id)

        id1 = (await new_channel.send(embed=rulesEmb)).id
        id2 = (await new_channel.send(embed=messageEmb, view=SuggestionView())).id
        config["suggest-message-id"] = [channel_id, [id1, id2]]
        with open("config.json", "w") as o:
            json.dump(config, o, indent=2)

        self.bot.log_action(f"[ADMIN] Suggestion module setup in channel {new_channel.id}", self.bot.admin_logger)
        await ctx.respond("Done", ephemeral=True)

    @tickets_sub.command(name="message")
    @option(name="channel", description="Where the message is sent", type=TextChannel, required=False)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_tickets_message(self, ctx: ApplicationContext, channel: TextChannel = None):
        if not channel:
            channel = ctx.channel

        await ctx.respond(f"Feature not implemented yet ! (Message will be sent in <#{channel.id}>)", ephemeral=True)

    @toggle_sub.command(name="turnip-buy")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_toggle_turnip_buy(self, ctx: ApplicationContext):
        with open("json/turnip.json", "r", encoding="utf-8") as turnip_file:
            turnip_settings = json.load(turnip_file)

        turnip_settings['can-buy'] = not turnip_settings['can-buy']

        with open("json/turnip.json", "w", encoding="utf-8") as turnip_file:
            json.dump(turnip_settings, turnip_file, indent=2)

        if turnip_settings['can-buy']:
            await ctx.respond("Players can now buy turnips", ephemeral=True)
            self.bot.log_action(f"[ADMIN] Turnips can now be bought", self.bot.eco_logger)
        else:
            await ctx.respond("Players can no longer buy turnips", ephemeral=True)
            self.bot.log_action(f"[ADMIN] Turnips can no longer be bought", self.bot.eco_logger)

    @toggle_sub.command(name="turnip-sell")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_toggle_turnip_sell(self, ctx: ApplicationContext):
        with open("json/turnip.json", "r", encoding="utf-8") as turnip_file:
            turnip_settings = json.load(turnip_file)

        turnip_settings['can-sell'] = not turnip_settings['can-sell']

        with open("json/turnip.json", "w", encoding="utf-8") as turnip_file:
            json.dump(turnip_settings, turnip_file, indent=2)

        if turnip_settings['can-sell']:
            await ctx.respond("Players can now sell turnips", ephemeral=True)
            self.bot.log_action(f"[ADMIN] Turnips can now be sold", self.bot.eco_logger)
        else:
            await ctx.respond("Players can no longer sell turnips", ephemeral=True)
            self.bot.log_action(f"[ADMIN] Turnips can no longer be sold", self.bot.eco_logger)

    @shop_sub.command(name="add_item")
    @option(name="object_id", description="The unique descriptor of the item", max_length=16)
    @option(name="price", description="The price of this item", min_value=0, max_value=4000000000)
    @option(name="object_type", description="What kind of item is it ?", choices=["coins", "xp", "ticket", "dummy", "toggle", "role"])
    @option(name="max_amount", description="", default=-1, min_value=-1, max_value=100)
    @option(name="ext_id", description="An external identifier corresponding to your item. (ex: role id, boost id)", default=None)
    @option(name="hidden", description="Do you want the item not to appear in the shop ?",
            choices=[OptionChoice(name="Yes", value=1), OptionChoice(name="No", value=0)], default=0)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_shop_add_item(self, ctx: ApplicationContext,
                                  object_id: str, 
                                  price: int,
                                  object_type: str,
                                  max_amount: int,
                                  ext_id: str,
                                  hidden: int):
        disabled = True
        if disabled:
            raise CommandDisabled("Need update")

        curA.execute(f"SELECT objectID FROM objects WHERE objectID = '{object_id}'")
        rowA = curA.fetchone()
        if rowA is not None:
            # todo: add custom view that ask if you want to edit the existing item
            #   data from this command is transmitted to the view via ctx.options (need testing tho)
            await ctx.respond(f"`{object_id}` already exist.")
            return

        curB.execute(f"INSERT INTO objects (objectID, price, maxAmount, objectType, extID, hidden) VALUES "
                     f"('{object_id}', {price}, {max_amount}, '{object_type}', '{ext_id}', {hidden})")
        db.commit()
        self.shop_items = None

        self.bot.log_action(f"[ADMIN] New item '{object_id}' added to the shop", self.bot.eco_logger)
        await ctx.respond(f"end of command", ephemeral=True)

    async def shop_remove_item_autocomplete(self, ctx: AutocompleteContext):
        obj_id = ctx.options['object_id']
        if self.shop_items is None:
            curA.execute("SELECT objectID FROM objects")
            items = []
            for item in curA.fetchall():
                items.append(item[0])
            self.shop_items = items
        else:
            items = self.shop_items
        return [item for item in items if obj_id in item]

    @shop_sub.command(name="remove_item")
    @option(name="object_id", description="The unique descriptor of the item you want to delete",
            autocomplete=shop_remove_item_autocomplete)
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_shop_remove_item(self, ctx: ApplicationContext, object_id: str):
        self.shop_items = None
        view = DeleteShopItemView(object_id=object_id, bot=self.bot)
        await ctx.respond(ephemeral=True, view=view)

    @admin_group.command(name="codes")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_codes(self, ctx: ApplicationContext):
        with open("json/codes.json", "r", encoding="utf-8") as code_file:
            codes = json.load(code_file)

        resume = []
        for code in codes:
            start = f"• {code}{(16 - len(code)) * ' '} :"
            count = f"{codes[code]['usage_count']}/{codes[code]['usage_limit'][0]}"
            mode = f"({codes[code]['usage_limit'][1]})"
            disabled = f"{(6 - len(mode)) * ' '}not" if codes[code]['disabled'] else ''
            resume.append(f"{start} {count} {(10 - len(count)) * ' '} {mode} {disabled}")

        # create a page system
        resume_text = ""
        for line in resume:
            if len(resume_text) + len(line) < 4000:
                resume_text += line + "\n"

        resume_text = "```py\n" + resume_text + "\n```"

        codes_emb = Embed(color=0x2b2d31, description=resume_text)
        codes_emb.set_author(name="Codes - Admin view")

        await ctx.respond(embed=codes_emb, view=AdminCodesView())

    # for the future command admin_codes_add here's the data structure of a usage_limit modification event :
    # data = {
    #     "type": "code-usage",
    #     "code": "insert_code_name",
    #     "limit": 0
    # }

    @commands.slash_command(name="maintenance", description="Disable or enable the use of a command globally")
    @option(name="command", description="The command you want to disable/enable")
    @option(name="reason", description="Why are you disabling it. Put anything if enabling.")
    @commands.is_owner()
    async def maintenance(self, ctx: ApplicationContext, command: str, reason: str):
        raw_commands = self.bot.application_commands
        command_list = []
        for cmd in raw_commands:
            if isinstance(cmd, SlashCommandGroup):
                for s1 in cmd.walk_commands():
                    if isinstance(s1, SlashCommandGroup):
                        for s2 in s1.walk_commands():
                            command_list.append(f"{s2.qualified_name}")
                    elif isinstance(s1, SlashCommand):
                        command_list.append(f"{s1.qualified_name}")

            elif isinstance(cmd, SlashCommand):
                command_list.append(f"{cmd.qualified_name}")

        if command in command_list:
            with open("json/disabled.json", "r", encoding="utf-8") as disabled_command_file:
                disabled_commands = json.load(disabled_command_file)

            if command in disabled_commands:
                del disabled_commands[command]
                await ctx.respond(f"Command is no longer disabled", ephemeral=True)
                self.bot.log_action(f"[ADMIN] Command '{command}' has been enabled by {ctx.author.id}",
                                    self.bot.admin_logger)

            else:
                data = {
                    "reason": reason,
                    "author": f"<@{ctx.author.id}>"
                }
                disabled_commands[command] = data
                await ctx.respond(f"Command `{command}` is now disabled because `{reason}`", ephemeral=True)
                self.bot.log_action(f"[ADMIN] Command '{command}' has been disabled by {ctx.author.id} for '{reason}'",
                                    self.bot.admin_logger)

            with open("json/disabled.json", "w", encoding="utf-8") as disabled_command_file:
                json.dump(disabled_commands, disabled_command_file, indent=2)

        else:
            await ctx.respond(f"Command `{command_list}` not found. To see all commands type `/admin commands list`.")

    @commands_sub.command(name="list")
    @commands.is_owner()
    @commands.check(is_disabled_check)
    async def admin_commands_list(self, ctx: ApplicationContext):
        raw_commands = self.bot.application_commands
        command_list = []
        for cmd in raw_commands:
            if isinstance(cmd, SlashCommandGroup):
                for s1 in cmd.walk_commands():
                    if isinstance(s1, SlashCommandGroup):
                        for s2 in s1.walk_commands():
                            command_list.append(f"{s2.qualified_name}")
                    elif isinstance(s1, SlashCommand):
                        command_list.append(f"{s1.qualified_name}")

            elif isinstance(cmd, SlashCommand):
                command_list.append(f"{cmd.qualified_name}")

        command_list = str(command_list)
        if len(command_list) > 2000:
            file, path = text_to_file(command_list, "command_list.txt")
            await ctx.respond("List was too long so I just sent you a file with the list in it !",
                              file=file, ephemeral=True)
            os.remove(path)
        else:
            await ctx.respond(command_list, ephemeral=True)


def setup(bot_):
    bot_.add_cog(Admin(bot_))
