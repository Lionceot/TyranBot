from discord import Embed, Color, User, ApplicationContext, Message, SlashCommandGroup, AutocompleteContext, \
    OptionChoice, Forbidden
from discord.ext import commands, tasks
from discord.commands import option

import json
from random import randint, choice
import asyncio
from dotenv import load_dotenv
from datetime import datetime, date


from main import MyBot, db, in_database, new_player
from custom_errors import NotEnoughMoney, IncorrectBetValue, UnknownSign, UserIsBot, UnknownObject, MaxAmountReached, \
    HowDidYouGetHere, TurnipFileError, TurnipPatternError, CantBuyTurnip, CantSellTurnip
from custom_views import PaymentView, ShopBrowserView
from custom_functions import key_with_lowest_value, sort_dict_by_value, get_parameter, time_now, get_text

load_dotenv()

curLang = db.cursor(buffered=True)  # cursor used to get the language setting in all the commands

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)
curD = db.cursor(buffered=True)
curE = db.cursor(buffered=True)
curF = db.cursor(buffered=True)
curG = db.cursor(buffered=True)


def get_inventory(user):
    curA.execute(f"SELECT objectID, amount FROM bag WHERE discordID = {user.id} and amount > 0")
    return [x for x in curA]


def get_boost(user: User, boost_type: str = "coins"):
    if not in_database(user):
        return 1

    now = round(time_now().timestamp())

    curA.execute(f"SELECT multiplier FROM active_boosts WHERE discordID = {user.id} and boostType = '{boost_type}' "
                 f"and endTimestamp > {now} ORDER BY multiplier DESC LIMIT 1")
    rowA = curA.fetchone()
    if rowA is not None:
        return rowA[0]
    return 1


class Economy(commands.Cog):
    """
        Toutes les commandes liées au système économique
    """

    def __init__(self, bot_: MyBot):
        self.bot = bot_
        self.bet_limit = get_parameter('bet_limit')

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'EconomyCog' has been loaded"
        self.bot.log_action(log_msg, self.bot.bot_logger)
        self.daily_loop.start()

    @tasks.loop(seconds=1)
    async def daily_loop(self):
        now = time_now()
        now_str = now.strftime("%H:%M:%S")

        if now_str == "00:00:00":
            # Allow everyone to use /daily and update their current streak
            curA.execute("UPDATE dailyrecord SET streak = 0 WHERE claimed = 0")
            curB.execute("UPDATE dailyrecord SET ready = 1, claimed = 0")
            self.bot.log_action(f"[ECO] Daily bonus available", self.bot.eco_logger)

            # Clear expired boosts
            curC.execute(f"DELETE FROM active_boosts WHERE endTimestamp < {round(now.timestamp())}")
            self.bot.log_action(f"[ECO] Expired boost removed from database", self.bot.eco_logger)

            # Apply changes
            db.commit()

    @daily_loop.before_loop
    async def before_daily_loop(self):
        self.bot.log_action("[LOOP] Daily loop has started.", self.bot.bot_logger)

    @daily_loop.after_loop
    async def after_daily_loop(self):
        self.bot.log_action("[LOOP] Daily loop has stopped.", self.bot.bot_logger)

    @commands.slash_command(name="coins", description="Indique la quantité d'argent d'un utilisateur.",
                            brief="Show a user's amount of money")
    @commands.guild_only()
    async def coins(self, ctx: ApplicationContext, user: User = None):
        if user:
            if user.bot:
                raise UserIsBot(user=user)

        else:
            user = ctx.author
            await new_player(user)

        currency_logo = get_parameter('currency-logo')

        if not in_database(user):
            await ctx.respond(f"{user.mention} • 0 {currency_logo}", ephemeral=True)
            return

        curA.execute(f"SELECT coins FROM users WHERE discordID = {user.id}")
        user_info = curA.fetchone()
        coins_amt = user_info[0]

        em = Embed(color=Color.default(), description=f"{user.mention} • {coins_amt} {currency_logo}")
        await ctx.respond(embed=em, ephemeral=True)

    @commands.message_command(name="Author's money")
    async def mc_coins(self, ctx, message: Message):
        user = message.author
        if user.bot:
            raise UserIsBot(user=user)

        currency_logo = get_parameter('currency-logo')

        if not in_database(user):
            await ctx.respond(f"{user.mention} • 0 {currency_logo}", ephemeral=True)
            return

        curA.execute(f"SELECT coins FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        coins_amt = rowA[0]

        em = Embed(color=Color.default(), description=f"{user.mention} • {coins_amt} {currency_logo}")
        await ctx.respond(embed=em, ephemeral=True)

    @commands.user_command(name="User's money")
    async def uc_coins(self, ctx, user: User):
        if user.bot:
            raise UserIsBot(user=user)
        if not in_database(user):
            await ctx.respond(f"{user.mention} doesn't have any coin", ephemeral=True)
            return

        curA.execute(f"SELECT coins FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        coins_amt = rowA[0]
        em = Embed(color=Color.default(), description=f"{user.mention} a {coins_amt} {get_parameter('currency-logo')}")
        await ctx.respond(embed=em, ephemeral=True)

    @commands.slash_command(name="leaderboard", description="Show the richest users", aliases=["lb", "richest"])
    async def leaderboard(self, ctx: ApplicationContext):
        # TODO: afficher le classement de user if in_database(user)
        #   vérifier la structure de curA après execution de la requete SQL et peut etre passer à un
        #   fetchall() et tout parcourir par indice. Cela impliquerait que l'erreur du except soit un IndexError.
        user = ctx.author

        curA.execute("SELECT discordID, coins FROM users ORDER BY coins DESC")

        lbEmb = Embed(color=Color.default(), title="Richest players",
                      description=f"This ranking is based on the number of {get_parameter('currency-logo')} you own. "
                                  f"It does not take into account purchased items.")

        medal_dict = {1: "first_place", 2: "second_place", 3: "third_place"}

        # les 3 premiers sont gérés individuellement pour mettre un émoji médaille devant leur nom
        for place in range(1, 4):
            try:
                rowA = curA.fetchone()
                user_id = rowA[0]
                user_name = (await self.bot.fetch_user(user_id)).display_name
                money = rowA[1]
                lbEmb.add_field(name=f":{medal_dict[place]}: {user_name}",
                                value=f"{get_parameter('currency-logo')} {money}",
                                inline=False)

            except TypeError:
                pass

        for place in range(4, 11):
            try:
                rowA = curA.fetchone()
                user_id = rowA[0]
                user_name = (await self.bot.fetch_user(user_id)).display_name
                money = rowA[1]
                lbEmb.add_field(name=f"{place} - {user_name}", value=f"{get_parameter('currency-logo')} {money}",
                                inline=False)

            except TypeError:
                pass

        await ctx.respond(embed=lbEmb, content=None)

    @commands.slash_command(name="daily", description="Claim your daily reward")
    @commands.guild_only()
    async def daily(self, ctx: ApplicationContext):
        # TODO : change bonus calculation with a dict
        user = ctx.author
        await new_player(user)

        curA.execute(
            f"SELECT d.streak, d.ready, d.nbDaily, d.bestStreak, u.language FROM dailyRecord AS d, users AS u WHERE d.discordID = {user.id} AND u.discordID = {user.id}")
        row = curA.fetchone()
        streak = row[0] + 1
        ready = row[1]
        best_streak = row[3]
        user_lang = row[4]

        if ready == 0:
            em = Embed(color=Color.red(), description=get_text("daily.already_done", user_lang))
            await ctx.respond(embed=em, ephemeral=True)
            return

        streak_bonuses = {
            365: 3,
            180: 2.5,
            30: 2,
            7: 1.25,
            1: 1
        }

        for x in [365, 180, 30, 7]:
            if streak >= x:
                streak_factor = streak_bonuses[x]
                break
        else:
            streak_factor = 1

        boost = get_parameter("global_coins_boost") * get_boost(user, "coins")
        earnings = int(round(randint(50, 120) * streak_factor) * boost)
        nbDaily = min(7, row[2] + 1)

        curB.execute(
            f"UPDATE DailyRecord SET streak = {streak}, ready = 0, claimed = 1, nbDaily = {nbDaily}, "
            f"bestStreak = {max(streak, best_streak)} WHERE discordID = {user.id}")
        curC.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
        db.commit()

        currency_logo = get_parameter('currency-logo')

        response_text = get_text(f"daily.claim {earnings} ({boost})", user_lang)
        # Replace placeholders by variables values
        # Replace placeholders by variables values

        if nbDaily >= 7:
            response_text = response_text.replace("%bonus_txt%", get_text("daily.bonus_ready", user_lang))
        else:
            response_text = response_text.replace("%bonus_txt%", "")

        em = Embed(color=Color.default(), description=response_text)
        await ctx.respond(embed=em)

    @commands.slash_command(description="A bonus earning every 7 /daily", guild_only=True)
    async def bonus(self, ctx: ApplicationContext):
        user = ctx.author

        curA.execute(f"SELECT d.nbDaily, u.language FROM dailyrecord as d join users as u on u.discordID = d.discordID "
                     f"WHERE u.discordID = {user.id}")
        rowA = curA.fetchone()
        nbDaily = rowA[0]
        user_lang = rowA[1]

        if nbDaily < 7:
            response_text = get_text("bonus.not_ready", user_lang)
            # response_text.replace("%nbDaily%", nbDaily)
            await ctx.respond(response_text, ephemeral=True)

        else:
            earnings = 100 * get_parameter("global_coins_boost") * get_boost(user, "coins")
            curB.execute(f"UPDATE users AS u, dailyrecord AS d SET u.coins = u.coins + {earnings}, d.nbDaily = 0 "
                         f"WHERE u.discordID = {user.id} and d.discordID = {user.id} ")
            db.commit()

            response_text = get_text("bonus.success", user_lang)
            # response_text = response_text.replace("%amount%", f"{earnings} {get_parameter('currency-logo')}")
            await ctx.respond(response_text)

    @commands.slash_command(name="work", description="Récupérer votre salaire toutes les 3h.")
    @commands.guild_only()
    @commands.cooldown(1, 10800, commands.BucketType.user)
    async def work(self, ctx: ApplicationContext):
        user = ctx.author
        await new_player(user)

        earnings = randint(100, 200) * get_parameter("global_coins_boost") * get_boost(user, "coins")
        curA.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
        db.commit()

        await ctx.respond(f"You worked and earned {earnings} {get_parameter('currency-logo')}")

    @commands.slash_command(name="shop", description="Show the available things to buy")
    @commands.guild_only()
    @option(name="category", description="What section are you looking for ?", choices=["ranks", "colors", "perks"])
    async def shop(self, ctx: ApplicationContext, category: str = "home"):
        user = ctx.author
        await new_player(user)

        curLang.execute(f"SELECT language FROM users WHERE discordID = {user.id}")
        user_lang = curLang.fetchone()[0]
        currency_logo = get_parameter('currency-logo')

        if category == 'home':
            emb = Embed(color=Color.blurple(), description=get_text("shop.home.desc", user_lang)) \
                .set_author(name=get_text("shop.home.author", user_lang)) \
                .set_footer(text=get_text("shop.footer", user_lang))
            await ctx.respond(embed=emb, view=ShopBrowserView(category=category, lang=user_lang), ephemeral=True)
            return

        elif category == 'ranks':
            curA.execute(f"SELECT objectID, price, need AS need_extID "
                         f"FROM objects WHERE category='ranks' AND locked=0 AND exclusive=0;")
            rowsA = curA.fetchall()

            curB.execute(f"SELECT objectID, price, need AS need_extID "
                         f"FROM objects WHERE category='ranks' AND locked=0 AND exclusive=1;")
            rowsB = curB.fetchall()

            emb = Embed(color=Color.dark_magenta(), description=get_text("shop.ranks.desc", user_lang)) \
                .set_author(name=get_text("shop.ranks.author", user_lang)) \
                .set_footer(text=get_text("shop.footer", user_lang))

        elif category == 'colors':
            curA.execute(f"SELECT objectID, price, need "
                         f"FROM objects WHERE category='colors' AND locked=0 AND exclusive=0;")
            rowsA = curA.fetchall()

            curB.execute(f"SELECT objectID, price, need AS need_extID "
                         f"FROM objects WHERE category='colors' AND locked=0 AND exclusive=1;")
            rowsB = curB.fetchall()

            emb = Embed(color=Color.orange(), description=get_text("shop.colors.desc", user_lang)) \
                .set_author(name=get_text("shop.colors.author", user_lang)) \
                .set_footer(text=get_text("shop.footer", user_lang))

        elif category == 'perks':
            curA.execute(f"SELECT objectID, price, need "
                         f"FROM objects WHERE category='perks' AND locked=0 AND exclusive=0;")
            rowsA = curA.fetchall()

            curB.execute(f"SELECT objectID, price, need AS need_extID "
                         f"FROM objects WHERE category='perks' AND locked=0 AND exclusive=1;")
            rowsB = curB.fetchall()

            emb = Embed(color=Color.dark_blue(), description=get_text("shop.perks.desc", user_lang)) \
                .set_author(name=get_text("shop.perks.author", user_lang)) \
                .set_footer(text=get_text("shop.footer", user_lang))

        else:
            raise HowDidYouGetHere

        text = []
        for elt in rowsA:
            t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', user_lang)} - {elt[1]} {currency_logo}"
            if elt[2] is not None:
                t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', user_lang)}"
            text.append(t)

        text = "\n".join(text)

        if len(rowsB) > 0:
            exclu_text = []
            for elt in rowsB:
                t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', user_lang)} - {elt[1]} {currency_logo}"
                if elt[2] is not None:
                    t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', user_lang)}"
                exclu_text.append(t)

            exclu_text = "\n".join(exclu_text)
            emb.add_field(name=get_text("shop.exclusive_items", user_lang), value=exclu_text)

        emb.add_field(name=get_text("shop.global_items", user_lang), value=text, inline=False)

        await ctx.respond(embed=emb, view=ShopBrowserView(category=category, lang=user_lang), ephemeral=True)

    # Do not set as a static method
    async def buy_autocomplete(self, ctx: AutocompleteContext):
        item_id = ctx.options['item_id']
        curA.execute(f"SELECT objectID FROM objects WHERE objectID LIKE '%{item_id}%'")
        res = curA.fetchall()
        return [x[0] for x in res]

    @commands.slash_command(name="buy", description="Let you buy an item")
    @option(name="item_id", description="This item you want to buy", autocomplete=buy_autocomplete)
    @option(name="quantity", description="The amount of item you want ot buy", min_value=1)
    @commands.guild_only()
    async def buy(self, ctx: ApplicationContext, item_id: str, quantity: int = 1):
        user = ctx.author
        await new_player(user)

        curA.execute(f"SELECT language, coins FROM users WHERE discordID = {user.id}")
        curB.execute(f"SELECT price, maxAmount, objectType FROM objects WHERE objectID = '{item_id}'")

        user_info = curA.fetchone()
        user_lang = user_info[0]
        product = curB.fetchone()

        if not product:
            raise UnknownObject

        coins = user_info[1]
        price = product[0]
        max_amount = product[1]
        object_type = product[2]

        user_inv = get_inventory(user)

        if max_amount > -1:
            if max_amount == 0:
                raise MaxAmountReached

            for item in user_inv:
                if item[0] == item_id:
                    current_amount = item[1]
                    if current_amount >= max_amount:
                        raise MaxAmountReached

                    new_amount = current_amount + quantity
                    if new_amount > max_amount:
                        quantity -= new_amount - max_amount
                    possessed = True
                    break

            else:
                possessed = False

        else:
            for item in user_inv:
                if item[0] == item_id:
                    possessed = True
                    break
            else:
                possessed = False

        if coins < price:
            raise NotEnoughMoney

        curC.execute(f"UPDATE users SET coins = coins - {price * quantity} WHERE discordID = {user.id}")
        if possessed:
            curD.execute(f"UPDATE bag SET amount = amount + {quantity} "
                         f"WHERE discordID = {user.id} AND objectID = '{item_id}'")
        else:
            curD.execute(f"INSERT INTO bag (discordID, objectID, amount) VALUES ({user.id}, '{item_id}', {quantity})")
        db.commit()

        response_text = get_text("buy.success", user_lang)

        # response_text = response_text.replace("%item_name%", get_text(f"items.{item_id}.name", user_lang))
        # response_text = response_text.replace("%amount%", quantity)

        await ctx.respond(response_text)

        # TODO: send message to auto equip role/open a ticket to claim a reward
        if object_type == "role":
            pass
        elif object_type == "ticket":
            pass

    # Do not set as a static method
    async def use_autocomplete(self, ctx: AutocompleteContext):
        return [item[0] for item in get_inventory(ctx.interaction.user)]

    @commands.slash_command(name="use")
    @option(name="item_id", description="This item you want to buy", autocomplete=use_autocomplete)
    @commands.guild_only()
    async def use(self, ctx: ApplicationContext, item_id: str):
        user = ctx.author
        curA.execute(f"SELECT language FROM users WHERE discordID = {user.id}")

        user_lang = curA.fetchone()[0]
        user_inv = [item[0] for item in get_inventory(user)]

        if item_id not in user_inv:
            await ctx.respond(get_text("use.not_possessed", user_lang))
            return

        curB.execute(f"SELECT amount, used FROM bag WHERE discordID = {user.id} AND objectID = '{item_id}'")
        rowB = curB.fetchone()
        amount = rowB[0]
        used = rowB[1]

        if used == 1:
            await ctx.respond(get_text("use.already_used", user_lang), ephemeral=True)
            return

        curC.execute(f"SELECT objectType, extID FROM objects WHERE objectID = '{item_id}'")
        rowC = curC.fetchone()

        if rowC is None:
            await ctx.respond(get_text("use.unknown_object_in_inventory", user_lang))
            self.bot.log_action(f"Unhandled objectID for item {item_id} in {user}s inventory", self.bot.shop_logger, 40)
            return

        object_type = rowC[0]
        ext_id = rowC[1]

        if object_type == "role":
            guild = self.bot.get_guild(779602390415835156)
            role = guild.get_role(int(ext_id))
            await user.add_roles(role, reason=f"Using object {item_id}")
            await ctx.respond(get_text("use.role_added", user_lang), ephemeral=True)
            curD.execute(f"UPDATE bag SET used = 1 WHERE discordID = {user.id} AND objectID = '{item_id}'")
            db.commit()

        elif object_type == "ticket":
            # TODO: update when tickets will be available
            await ctx.respond(get_text("command.feature_not_added", user_lang), ephemeral=True)

        elif object_type == "toggle":
            await ctx.respond(get_text("use.toggle", user_lang), ephemeral=True)

        elif object_type == "dummy":
            await ctx.respond(get_text("use.no_use", user_lang), ephemeral=True)

        elif object_type == "coins":
            curD.execute(f"SELECT duration, multiplier FROM boosts WHERE boostID = '{ext_id}'")
            rowD = curD.fetchone()
            duration = rowD[0]
            multiplier = rowD[1]

            curE.execute(f"SELECT multiplier, endTimestamp FROM active_boosts "
                         f"WHERE discordID = {user.id} AND boostType = 'coins' AND multiplier = {multiplier}")
            rowE = curE.fetchone()

            if rowE is None:
                curF.execute(f"INSERT INTO active_boosts (discordID, endTimestamp, multiplier, boostType) "
                             f"VALUES ({user.id}, {int(time_now().timestamp()) + duration}, {multiplier}, 'coins')")
            else:
                curF.execute(f"UPDATE active_boosts SET endTimestamp = endTimestamp + {duration} "
                             f"WHERE discordID = {user.id} AND boostType = 'coins' AND multiplier = {multiplier}")

            if amount == 1:
                curG.execute(f"DELETE FROM bag WHERE discordID = {user.id} AND objectID = '{item_id}'")
            else:
                curG.execute(
                    f"UPDATE bag SET amount = amount - 1 WHERE discordID = {user.id} AND objectID = '{item_id}'")
            db.commit()
            await ctx.respond(get_text("use.boost_used", user_lang), ephemeral=True)

        elif object_type == "xp":
            curD.execute(f"SELECT duration, multiplier FROM boosts WHERE boostID = '{ext_id}'")
            rowD = curD.fetchone()
            duration = rowD[0]
            multiplier = rowD[1]

            curE.execute(f"SELECT multiplier, endTimestamp FROM active_boosts "
                         f"WHERE discordID = {user.id} AND boostType = 'xp' AND multiplier = {multiplier}")
            rowE = curE.fetchone()

            if rowE is None:
                curF.execute(f"INSERT INTO active_boosts (discordID, endTimestamp, multiplier, boostType) "
                             f"VALUES ({user.id}, {int(time_now().timestamp()) + duration}, {multiplier}, 'xp')")
            else:
                curF.execute(f"UPDATE active_boosts SET endTimestamp = endTimestamp + {duration} "
                             f"WHERE discordID = {user.id} AND boostType = 'xp' AND multiplier = {multiplier}")

            if amount == 1:
                curG.execute(f"DELETE FROM bag WHERE discordID = {user.id} AND objectID = '{item_id}'")
            else:
                curG.execute(
                    f"UPDATE bag SET amount = amount - 1 WHERE discordID = {user.id} AND objectID = '{item_id}'")

            db.commit()
            await ctx.respond(get_text("use.boost_used", user_lang), ephemeral=True)

        else:
            await ctx.respond(get_text("use.unhandled_objectType", user_lang))
            self.bot.log_action(f"Unhandled objectID for item {item_id}", self.bot.shop_logger, 40)

    @commands.slash_command(name="inventory", description="See someone's inventory")
    @option(name="user", description="Who do you want to see the inventory ?")
    async def inventory(self, ctx, user: User = None):
        """
        Show someone's inventory

        :param ctx: Command context
        :param user: The user you want to the inventory
        :return:
        """
        if not user:
            user = ctx.author

        if user.bot:
            raise UserIsBot(user=user)

        curLang.execute(f"SELECT language FROM users WHERE discordID = {user.id}")

        user_lang = curLang.fetchone()[0]
        user_inv = get_inventory(user)

        invEmb = Embed(color=Color.blurple())
        invEmb.set_author(name=get_text("inventory.title", user_lang))

        if len(user_inv) == 0:
            invEmb.add_field(name="\u200b", value=get_text("inventory.no_item", user_lang))
        else:
            items = [f"{get_text(f'items.{item[0]}.name', user_lang)} - x{item[1]}" for item in user_inv]
            invEmb.add_field(name="\u200b", value="\n".join(items))
        await ctx.respond(embed=invEmb, ephemeral=True)

    @commands.user_command(name="User's inventory")
    async def uc_inventory(self, ctx, user: User):
        if user.bot:
            raise UserIsBot(user=user)

        curLang.execute(f"SELECT language FROM users WHERE discordID = {user.id}")

        user_lang = curLang.fetchone()[0]
        user_inv = get_inventory(user)

        invEmb = Embed(color=Color.blurple())
        invEmb.set_author(name=get_text("inventory.title", user_lang))

        if len(user_inv) == 0:
            invEmb.add_field(name="\u200b", value=get_text("inventory.no_item", user_lang))
        else:
            items = [f"{get_text(f'items.{item[0]}.name', user_lang)} - x{item[1]}" for item in user_inv]
            invEmb.add_field(name="\u200b", value="\n".join(items))
        await ctx.respond(embed=invEmb, ephemeral=True)

    #
    @commands.message_command(name="Author's inventory", description="Voir les objets possédés",
                              brief="Show a user's inventory")
    async def mc_inventory(self, ctx, message: Message):
        user = message.author
        if user.bot:
            raise UserIsBot(user=user)

        curLang.execute(f"SELECT language FROM users WHERE discordID = {user.id}")

        user_lang = curLang.fetchone()[0]
        user_inv = get_inventory(user)

        invEmb = Embed(color=Color.blurple())
        invEmb.set_author(name=get_text("inventory.title", user_lang))

        if len(user_inv) == 0:
            invEmb.add_field(name="\u200b", value=get_text("inventory.no_item", user_lang))
        else:
            items = [f"{get_text(f'items.{item[0]}.name', user_lang)} - x{item[1]}" for item in user_inv]
            invEmb.add_field(name="\u200b", value="\n".join(items))
        await ctx.respond(embed=invEmb, ephemeral=True)

    @commands.slash_command(name="pay", description="Give money to someone.")
    @option(name="receiver", type=User)
    @option(name="amount", min_value=1)
    @commands.guild_only()
    async def pay(self, ctx: ApplicationContext, receiver: User, amount: int):
        if receiver.bot:
            raise UserIsBot(user=receiver)

        sender = ctx.author
        await new_player(sender)

        if not in_database(receiver):
            await ctx.respond(f"Oops, it seems like {receiver.mention} never used my commands. Please wait until they"
                              f"have done so.", ephemeral=True)
            return

        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {sender.id}")  # get sender money amt
        row = curA.fetchone()
        money = row[0]
        user_lang = row[1]

        if amount > money:
            raise NotEnoughMoney

        elif amount == money:  # you're trying to give all your money
            pay_view = PaymentView(sender=sender, receiver=receiver, amount=amount, lang=user_lang)
            await ctx.respond(f":warning: Are you sure you want to give ALL your money to {receiver} ?", view=pay_view,
                              ephemeral=True)

        else:  # regular operation
            curB.execute(f"UPDATE users SET coins = {money - amount} WHERE discordID = {sender.id}")
            curC.execute(f"UPDATE users SET coins = coins + {amount} WHERE discordID = {receiver.id}")
            db.commit()
            response_text = get_text("pay.success", user_lang)
            # response_text = response_text.replace("%amount%", f"{amount} {get_parameter('currency-logo')}")
            # response_text = response_text.replace("%receiver%", receiver.mention)
            await ctx.respond(f"❱❱ You just gave {amount} {get_parameter('currency-logo')} to {receiver.mention}.")

    @commands.slash_command(name="dice", description="Play dice", guild_only=True)
    @option(name="bet", description="How much would you gamble ?", min_amt=1, max_value=get_parameter('bet_limit'),
            required=False)
    # @commands.cooldown(1, 1800, commands.BucketType.user)
    async def dice(self, ctx: ApplicationContext, bet: int = None):
        user = ctx.author
        await new_player(user)

        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        money = rowA[0]
        user_lang = rowA[1]

        if bet:
            if not (1 <= bet <= self.bet_limit):
                self.dice.reset_cooldown(ctx)
                raise IncorrectBetValue

            elif bet > money:
                self.dice.reset_cooldown(ctx)
                raise NotEnoughMoney

        else:
            bet = 0

        await ctx.respond(get_text("dice.start", user_lang))

        currency_logo = get_parameter('currency-logo')
        j1, j2 = randint(1, 6), randint(1, 6)

        if j1 + j2 == 12:
            earnings = bet * 3 * get_parameter("global_coins_boost") * get_boost(user, "coins")
            text_1 = get_text("dice.double_6.part_1", user_lang)
            text_2 = get_text("dice.double_6.part_2", user_lang)
            text_3 = get_text("dice.win", user_lang)

            curB.execute(
                f"UPDATE stats SET dicePlayed=dicePlayed+1, diceWon=diceWon+1, coinsBetInGames=coinsBetInGames+{bet}, coinsWonInGames=coinsWonInGames+{earnings} "
                f"WHERE discordID = {user.id}")

        else:
            b1, b2 = randint(1, 6), randint(1, 6)

            text_1 = get_text("dice.regular.part_1", user_lang)
            text_2 = get_text("dice.regular.part_2", user_lang)

            if j1 + j2 < b1 + b2:
                text_3 = get_text("dice.lose", user_lang)
                earnings = -bet
                curB.execute(f"UPDATE stats SET dicePlayed=dicePlayed+1, coinsBetInGames=coinsBetInGames+{bet}, "
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID = {user.id}")

            elif j1 + j2 > b1 + b2:
                if j1 == j2:
                    earnings = bet * 2 * get_parameter("global_coins_boost") * get_boost(user, "coins")
                else:
                    earnings = bet * get_parameter("global_coins_boost") * get_boost(user, "coins")

                text_3 = get_text("dice.win", user_lang)
                curB.execute(f"UPDATE stats SET dicePlayed=dicePlayed+1, diceWon=diceWon+1, "
                             f"coinsBetInGames=coinsBetInGames+{bet}, coinsWonInGames=coinsWonInGames+{earnings} "
                             f"WHERE discordID = {user.id}")

            else:
                text_3 = get_text("dice.draw", user_lang)
                earnings = 0
                curB.execute(f"UPDATE stats SET dicePlayed=dicePlayed+1, coinsBetInGames=coinsBetInGames+{bet} "
                             f"WHERE discordID = {user.id}")

            await ctx.send(text_1)
            await asyncio.sleep(1.5)
            await ctx.send(text_2)
            await asyncio.sleep(1.5)
            await ctx.send(text_3)

            curC.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
            db.commit()

    @commands.slash_command(name="guess", description="Try to guess what number I'm thinking of", brief="Guessing game",
                            guild_only=True)
    @option(name="bet", description="How much would you gamble ?", min_amt=1, max_value=get_parameter('bet_limit'))
    # @commands.cooldown(1, 3600, commands.BucketType.user)
    async def guess(self, ctx: ApplicationContext, bet: int = None):
        disabled = True
        if disabled:
            disabled_emb = Embed(color=Color.orange(), description=":construction: Command is disabled :construction:")
            await ctx.respond(embed=disabled_emb, ephemeral=True)
            return

        user = ctx.author
        await new_player(user)

        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        user_coins = rowA[0]
        user_lang = rowA[1]


        if bet:
            if not (1 <= bet <= self.bet_limit):
                self.dice.reset_cooldown(ctx)
                raise IncorrectBetValue

            elif bet > user_coins:
                self.dice.reset_cooldown(ctx)
                raise NotEnoughMoney

        else:
            self.guess.reset_cooldown(ctx)

        goal = randint(1, 100)
        attempts = 0
        canceled = False
        lost = False

        await ctx.respond(get_text("guess.start", user_lang))

        while attempts < 5:
            try:
                response: Message = await self.bot.wait_for('message', check=lambda message:
                                                            message.author == ctx.author and
                                                            message.channel == ctx.channel, timeout=30)
                print(type(response))
                print(type(response.content))
                print("|_" + response.content + "_|")
                print(response)
                guess = int(response.content)
                attempts += 1

                if guess == goal:
                    break

                elif guess < goal:
                    await ctx.send(get_text("guess.lower", user_lang))

                else:
                    await ctx.send(get_text("guess.higher", user_lang))

                if attempts == 5:
                    lost = True

            except asyncio.TimeoutError:
                print("timeout")
                return

            except ValueError:
                await ctx.send(get_text("guess.incorrect_value", user_lang))
                continue

        if canceled:
            pass

        elif bet:
            if lost:
                await ctx.send(get_text("guess.lost", user_lang))
                curB.execute(f"UPDATE users SET coins = coins-{bet} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET guessPlayed=guessPlayed+1, coinsBetInGames=coinsBetInGames+{bet}, "
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID = {user.id}")

            else:
                reward_dict = {
                    # "attempts_amount (int)": "reward multiplier (int/float)"
                    1: 10,
                    2: 5,
                    3: 3,
                    4: 2,
                    5: 1
                }
                reward = bet * reward_dict[attempts] * get_boost(user, "coins")

                await ctx.send(get_text("guess.win", user_lang))

                curB.execute(f"UPDATE users SET coins = coins+{reward} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET guessPlayed=guessPlayed+1, guessWon=guessWon+1, "
                             f"coinsBetInGames=coinsInGames+{bet}, coinsWonInGames=coinsWonInGames+{reward} "
                             f"WHERE discordID={user.id}")

        else:
            if lost:
                await ctx.send(get_text("guess.no_bet.lost", user_lang))
                curB.execute(f"UPDATE stats SET guessPlayed=guessPlayed+1, WHERE discordID = {user.id}")

            else:
                await ctx.send(get_text("guess.no_bet.win", user_lang))
                curB.execute(f"UPDATE stats SET guessPlayed=guessPlayed+1, guessWon=guessWon+1, "
                             f"WHERE discordID={user.id}")

        db.commit()

    @commands.slash_command(name="coinflip", guild_only=True)
    @option(name="side", description="Which side are you on ?", choices=[
        OptionChoice(name="face", value="head"),
        OptionChoice(name="pile", value="tail")])
    @option(name="bet", description="How much money will you gamble ?", max_value=get_parameter('bet_limit'))
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def coinflip(self, ctx: ApplicationContext, side: str, bet: int = None):
        user = ctx.author
        await new_player(user)

        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        user_coins = rowA[0]
        user_lang = rowA[1]
        result = choice(["head", "tail"])

        await ctx.respond(get_text("coinflip.start", user_lang))
        await asyncio.sleep(1.5)
        await ctx.send(get_text("coinflip.result", user_lang))
        await asyncio.sleep(1)

        if bet:
            if not 1 <= bet <= self.bet_limit:
                self.coinflip.reset_cooldown(ctx)
                raise IncorrectBetValue

            elif bet > user_coins:
                self.coinflip.reset_cooldown(ctx)
                raise NotEnoughMoney

            if result != side:
                curB.execute(f"UPDATE users SET coins = coins - {bet} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET coinflipPlayed=coinflipPlayed+1, coinsBetInGames=coinsBetInGames+{bet},"
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID={user.id}")
                await ctx.send(get_text("coinflip.lose", user_lang))

            else:
                earnings = bet * get_parameter('global_coins_boost') * get_boost(user, "coins")
                curB.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
                curC.execute(
                    f"UPDATE stats SET coinflipPlayed=coinflipPlayed+1, coinflipWon=coinflipWon+1, "
                    f"coinsBetInGames=coinsBetInGames+{bet},coinsWonInGames=coinsWonInGames+{earnings} "
                    f"WHERE discordID={user.id}")
                await ctx.send(get_text("coinflip.win", user_lang))

        else:
            self.coinflip.reset_cooldown(ctx)
            if result != side:
                curB.execute(f"UPDATE stats SET coinflipPlayed=coinflipPlayed+1 WHERE discordID={user.id}")
                await ctx.send(get_text("coinflip.no_bet.lose", user_lang))

            else:
                curB.execute(f"UPDATE stats SET coinflipPlayed=coinflipPlayed+1, coinflipWon=coinflipWon+1 "
                             f"WHERE discordID={user.id}")
                await ctx.send(get_text("coinflip.no_bet.win", user_lang))

        db.commit()

    @commands.slash_command(name="rps", description="Play rock paper scissors", brief="A game of rock paper scissors",
                            guild_only=True)
    @option(name="sign", description="What sign will you choose ?", choices=["rock", "paper", "scissors"])
    @option(name="bet", description="How much would you gamble ?", min_amt=1,
            max_value=get_parameter('bet_limit'), required=False)
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def rps(self, ctx: ApplicationContext, sign: str, bet: int):
        user = ctx.author
        await new_player(user)

        if bet:
            curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
            rowA = curA.fetchone()
            money = rowA[0]
            user_lang = rowA[1]

            if not 1 <= bet <= self.bet_limit:
                self.dice.reset_cooldown(ctx)
                raise IncorrectBetValue

            elif bet > money:
                self.dice.reset_cooldown(ctx)
                raise NotEnoughMoney

            currency_logo = get_parameter('currency-logo')

        else:
            self.dice.reset_cooldown(ctx)
            curA.execute(f"SELECT language FROM users WHERE discordID = {user.id}")
            rowA = curA.fetchone()
            user_lang = rowA[0]

        bot_sign = choice(["rock", "paper", "scissors"])
        if sign == "paper":
            if bot_sign == "paper":
                score = 2
            elif bot_sign == "rock":
                score = 1
            else:
                score = 0
        elif sign == "rock":
            if bot_sign == "paper":
                score = 0
            elif bot_sign == "rock":
                score = 2
            else:
                score = 1
        elif sign == "scissors":
            if bot_sign == "paper":
                score = 1
            elif bot_sign == "rock":
                score = 0
            else:
                score = 2

        else:
            raise UnknownSign

        await ctx.respond(get_text("rps.player_play", user_lang))
        await asyncio.sleep(1.5)
        await ctx.send(get_text("rps.bot_play", user_lang))
        await asyncio.sleep(1.5)

        if bet:
            if score == 0:
                curB.execute(f"UPDATE users SET coins = coins - {bet} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, coinsBetInGames=coinsBetInGames+{bet}, "
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID={user.id}")
                await ctx.send(get_text("rps.lose", user_lang))
            elif score == 1:
                earnings = bet * get_parameter("global_coins_boost") * get_boost(user, "coins")
                curB.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
                curC.execute(
                    f"UPDATE stats SET rpsPlayed=rpsPlayed+1, rpsWon=rpsWon+1, coinsBetInGames=coinsBetInGames+{bet},"
                    f"coinsWonInGames=coinsWonInGames+{earnings} WHERE discordID={user.id}")
                await ctx.send(get_text("rps.win", user_lang))
            else:
                curC.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, coinsBetInGames=coinsBetInGames+{bet} "
                             f"WHERE discordID={user.id}")
                await ctx.send(get_text("rps.draw", user_lang))

        else:
            if score == 0:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.lose", user_lang))
            elif score == 1:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, rpsWon=rpsWon+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.win", user_lang))
            else:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.draw", user_lang))
        db.commit()

    @staticmethod
    def get_stat_emb(user: User):
        stats_arg = [
            "s.rpsPlayed", "s.rpsWon",
            "s.dicePlayed", "s.diceWon",
            "s.guessPlayed", "s.guessWon",
            "s.coinflipPlayed", "s.coinflipWon",
            "s.coinsBetInGames", "s.coinsWonInGames", "s.coinsLostInGames",
            "s.mostPotatoBought", "s.mostPotatoSold", "s.mostPotatoRotten", "s.mostCoinsLostInPotato",
            "d.bestStreak"
        ]
        curA.execute(
            f"SELECT {','.join(stats_arg)} FROM stats AS s "
            f"JOIN dailyrecord AS d ON d.discordID = s.discordID "
            f"WHERE s.discordID = {user.id} GROUP BY s.discordID")
        rowA = curA.fetchone()

        rpsPlayed = rowA[0]
        rpsWon = rowA[1]
        dicePlayed = rowA[2]
        diceWon = rowA[3]
        guessPlayed = rowA[4]
        guessWon = rowA[5]
        coinflipPlayed = rowA[6]
        coinflipWon = rowA[7]
        coinsBetInGames = rowA[8]
        coinsWonInGames = rowA[9]
        coinsLostInGames = rowA[10]
        mostPotatoBought = rowA[11]
        mostPotatoSold = rowA[12]
        mostPotatoRotten = rowA[13]
        mostCoinsLostInPotato = rowA[14]
        bestDailyStreak = rowA[15]

        currency_logo = get_parameter('currency-logo')

        statEmb = Embed(color=Color.blurple())
        statEmb.set_author(name=f"{user.display_name}")
        statEmb.set_footer(text=f"『Stats』     『TyranBot』•『{get_parameter('version')}』")
        statEmb.add_field(
            name="Jeux",
            value=f"• Rps : {rpsPlayed} ({round(rpsWon / rpsPlayed * 100, 2) if rpsPlayed != 0 else 'N/A'}%) \n"
                  f"• Dice : {dicePlayed} ({round(diceWon / dicePlayed * 100, 2) if dicePlayed != 0 else 'N/A'}%) \n"
                  f"• Guess : {guessPlayed} ({round(guessWon / guessPlayed * 100, 2) if guessPlayed != 0 else 'N/A'}%) \n"
                  f"• Coinflip : {coinflipPlayed} ({round(coinflipWon / coinflipPlayed * 100, 2) if coinflipPlayed != 0 else 'N/A'}%)",
            inline=False
        )
        statEmb.add_field(
            name="Argent",
            value=f"• Parié : {coinsBetInGames}{currency_logo} \n"
                  f"• Gagné : {coinsWonInGames}{currency_logo} \n"
                  f"• Perdu : {coinsLostInGames}{currency_logo} \n"
                  f"• Meilleur daily streak : {bestDailyStreak} jours"
        )
        statEmb.add_field(name="Patate",
                          value=f"• Le plus grand nombre acheté en une semaine : {mostPotatoBought} \n"
                                f"• La plus grande vente : {mostPotatoSold} \n"
                                f"• Le plus de patate pourrie : {mostPotatoRotten} \n"
                                f"• Le plus d'argent perdu : {mostCoinsLostInPotato}")
        return statEmb

    @commands.slash_command(name="stats", brief="Shows you the stats of someone", usage="")
    async def stats(self, ctx: ApplicationContext, user: User = None):
        if not user:
            user = ctx.author

        if user.bot:
            raise UserIsBot(user=user)

        if not in_database(user):
            await ctx.respond(get_text("stats.no_stat", ""), ephemeral=True)

        statEmb = self.get_stat_emb(user)

        await ctx.respond(embed=statEmb)

    @commands.message_command(name="Stats")
    async def mc_stats(self, ctx: ApplicationContext, message: Message):
        user = message.author
        if user.bot:
            raise UserIsBot(user=user)

        if not in_database(user):
            await ctx.respond(get_text("stats.no_stat", ""), ephemeral=True)
        statEmb = self.get_stat_emb(user)
        await ctx.respond(embed=statEmb)

    @commands.user_command(name="Stats")
    async def uc_stats(self, ctx: ApplicationContext, user: User):
        if user.bot:
            raise UserIsBot(user=user)

        if not in_database(user):
            await ctx.respond(get_text("stats.no_stat", ""), ephemeral=True)
        statEmb = self.get_stat_emb(user)
        await ctx.respond(embed=statEmb)


class Turnip(commands.Cog):
    """
        Fonctions liées au cours du navet
        based on :
        https://docs.google.com/document/d/1bSVNpOnH_dKxkAGr718-iqh8s8Z0qQ54L-0mD-lbrXo/edit#heading=h.plkfxg2erbyb
    """

    def __init__(self, bot_: MyBot):
        self.bot = bot_

        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)

        self.resetting = False

        self.week_started = data['week-started']
        self.week_started_timestamp = round(datetime.strptime(self.week_started, "%Y-%m-%d").timestamp())

        self.half_day = data["half-day"]
        self.time_end_hd = self.week_started_timestamp + (self.half_day+1) * 3600 * 12

        self.can_buy = self.half_day < 3
        self.buy_price = data['base-price']

        self.can_sell = not self.can_buy
        if self.half_day < 14:
            self.sell_price = data['prices'][self.half_day]
        else:
            self.sell_price = 0
        self.mid_week_start = False

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'TurnipCog' has been loaded"
        self.bot.log_action(log_msg, self.bot.bot_logger)

        self.turnip_loop.start()

    @tasks.loop(seconds=10)
    async def turnip_loop(self):
        now_timestamp = time_now().timestamp()

        # Si le processus de nouvelle semaine est déjà en route, on ne le relance pas
        if self.resetting:
            return

        # on compare les temps pour savoir si on a changé de demi-journée
        if now_timestamp > self.time_end_hd:
            today = date.today().strftime("%a")

            # check if it has been 7 days or more since last update
            if now_timestamp - self.week_started_timestamp >= 3600 * 24 * 7:
                self.mid_week_start = today != 'Sun'
                self.bot.log_action(f"[TURNIP] Starting new week reset.", self.bot.turnip_logger)
                await self.new_week(now_timestamp)
                self.bot.log_action(f"[TURNIP] New week reset finished.", self.bot.turnip_logger)

            elif today == 'Sun':  # si on est dimanche et que ça fait moins d'une semaine rien à faire
                pass

            else:  # si on n'est pas dimanche on fait les modifications nécessaires
                with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
                    data = json.load(turnip_file)
                self.half_day = int((now_timestamp - self.week_started_timestamp) // (3600*12))
                data["half-day"] = self.half_day
                self.sell_price = data['prices'][self.half_day]
                with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
                    json.dump(data, turnip_file, indent=2)

    @turnip_loop.before_loop
    async def before_turnip_loop(self):
        self.bot.log_action("[LOOP] Turnip loop has started.", self.bot.bot_logger)

    @turnip_loop.after_loop
    async def after_turnip_loop(self):
        self.bot.log_action("[LOOP] Turnip loop has stopped.", self.bot.bot_logger)

    async def new_week(self, now_tmp: int):
        """ Save the last week's data and generate new settings for the upcoming one """
        self.resetting = True

        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            turnip_settings = json.load(turnip_file)
            start_date = turnip_settings['week-started']

        # Setting the new week-started
        a_week = 3600 * 24 * 7
        end_week_timestamp = self.week_started_timestamp + a_week
        nb_week = (now_tmp - end_week_timestamp) // a_week
        new_week_started_tmp = end_week_timestamp + nb_week * a_week
        new_week_started = datetime.fromtimestamp(new_week_started_tmp).strftime("%Y-%m-%d")
        half_day = int((now_tmp - new_week_started_tmp) // (3600 * 12))
        can_buy = half_day < 3
        can_sell = not can_buy

        self.bot.log_action(f"[TURNIP] Saving past week data", self.bot.turnip_logger)
        await self.save_user_data(start_date)

        # generating new values for the new week
        self.bot.log_action(f"[TURNIP] Generating upcoming week data", self.bot.turnip_logger)
        pattern = self.new_pattern(turnip_settings['last-pattern'], turnip_settings['patterns-chances'])
        durations = self.phases_duration(pattern)
        base_price, final_prices = self.phases_prices(pattern, durations)

        # Updating file
        turnip_settings['last-pattern'] = turnip_settings['pattern']
        turnip_settings['pattern'] = pattern
        turnip_settings['base-price'] = base_price
        turnip_settings['durations'] = durations
        turnip_settings['prices'] = final_prices
        turnip_settings['week-started'] = new_week_started
        turnip_settings['half-day'] = half_day
        with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
            json.dump(turnip_settings, turnip_file, indent=2)

        # Updating cached values
        self.bot.log_action(f"[TURNIP] Caching new values", self.bot.turnip_logger)
        self.half_day = half_day
        self.time_end_hd = (half_day + 1) * 3600 * 12 + new_week_started_tmp
        self.week_started = new_week_started
        self.week_started_timestamp = new_week_started_tmp
        self.can_buy = can_buy
        self.can_sell = can_sell
        self.resetting = False

    async def save_user_data(self, start_date):
        currency_logo, bot_version, lb_role, lb_channel, turnip_logo = get_parameter(
            ['currency-logo', 'version', 'turnip-leaderboard-role', 'turnip-leaderboard-channel', 'turnip-emote']
        )

        # Querying data from the DB
        selected_data = ["discordID", "turnipBought", "turnipSold", "coinsFromTurnip", "coinsIntoTurnip", "recap"]
        curA.execute(f"SELECT {', '.join(selected_data)} FROM turnip WHERE turnipBought > 0")
        rowsA = curA.fetchall()

        # Creating new file to save the week's data
        logs = {}

        # Leaderboard categories
        most_earned = {"id": -1, "id2": -1, "id3": -1}
        most_lost = {"id": -1, "id2": -1, "id3": -1}
        most_rotten = {"id": -1, "id2": -1, "id3": -1}
        most_bought = {"id": -1, "id2": -1, "id3": -1}

        #
        for user_data in rowsA:
            user_id = user_data[0]
            turnip_bought = user_data[1]
            turnip_sold = user_data[2]
            rotten = turnip_bought - turnip_sold
            earnings = user_data[3]
            expenses = user_data[4]
            loss = abs(earnings - expenses) if earnings - expenses < 0 else 0
            recap = user_data[5] == 1

            if turnip_bought > 0:
                logs[user_id] = {
                    "turnip_bought": turnip_bought,
                    "turnip_sold": turnip_sold,
                    "coinsFromTurnip": earnings,
                    "coinsIntoTurnip": expenses
                }

            if recap:
                # todo_later: need language parameter
                user = self.bot.get_user(user_id)

                recap_emb = Embed(color=0xf6f0de)
                recap_emb.set_author(name=f"Semaine du {'/'.join(reversed(start_date.split('-')))}",
                                     icon_url=user.avatar)
                recap_emb.add_field(name="Achats", value=f"- {turnip_logo} {turnip_bought}\n"
                                                         f"- {currency_logo} {expenses}")
                recap_emb.add_field(name="Ventes", value=f"- {turnip_logo} {turnip_sold}\n"
                                                         f"- {currency_logo} {earnings}")

                if loss > 0:
                    total_msg = f"{loss} perdu{'s' if loss > 1 else ''}"

                else:
                    total_msg = f"{earnings - expenses} gagné{'s' if earnings - expenses > 1 else ''}"

                recap_emb.add_field(name="Total", value=f"- {turnip_logo} {rotten} pourri{'s' if rotten > 1 else ''} \n"
                                                        f"- {currency_logo} {total_msg}",
                                    inline=False)
                recap_emb.set_footer(text=f"『Recap』     『TyranBot』•『{bot_version}』")

                try:
                    await user.send(embed=recap_emb)
                except Forbidden:
                    pass

            lowest_track = key_with_lowest_value(most_lost)
            if most_lost[lowest_track] < loss:
                del most_lost[lowest_track]
                most_lost[user_id] = loss

            lowest_track = key_with_lowest_value(most_rotten)
            if most_rotten[lowest_track] < rotten:
                del most_rotten[lowest_track]
                most_rotten[user_id] = rotten

            lowest_track = key_with_lowest_value(most_bought)
            if most_bought[lowest_track] < turnip_bought:
                del most_bought[lowest_track]
                most_bought[user_id] = turnip_bought

            lowest_track = key_with_lowest_value(most_earned)
            if most_earned[lowest_track] < earnings:
                del most_earned[lowest_track]
                most_earned[user_id] = earnings

        with open(f"logs/turnip/{start_date}.json", 'w', encoding='utf-8') as turnip_log_file:
            json.dump(logs, turnip_log_file, indent=2)

        curB.execute(f"SELECT sum(turnipBought),sum(turnipSold),sum(coinsFromTurnip),sum(coinsIntoTurnip) FROM turnip")
        rowB = curB.fetchone()
        total_bought = rowB[0]
        total_sold = rowB[1]
        total_earned = rowB[2]
        total_spend = rowB[3]

        lead_emb = Embed(color=0x61ad3c, title=f"Résumé de la semaine du {'/'.join(reversed(start_date.split('-')))}")

        leaderboards_1 = {
            "PeppaCoins gagnés": most_earned,
            "PeppaCoins perdus": most_lost
        }

        for key in leaderboards_1:
            users = []
            track = sort_dict_by_value(leaderboards_1[key], True)
            medal_dict = {1: "first_place", 2: "second_place", 3: "third_place"}
            counter = 0
            for user in track:
                if counter > 3:
                    break

                if track[user] > 0:
                    counter += 1
                    users.append(f":{medal_dict[counter]}: {currency_logo} {track[user]} - <@{user}>")
            lead_emb.add_field(name=key, value="\n".join(users))

        leaderboards_2 = {
            "Navet pourris": most_rotten,
            "Navet achetés": most_bought
        }

        lead_emb.add_field(name="\u200b", value="\u200b")

        for key in leaderboards_2:
            users = []
            track = sort_dict_by_value(leaderboards_2[key], True)
            medal_dict = {1: "first_place", 2: "second_place", 3: "third_place"}
            counter = 0
            for user in track:
                if counter > 3:
                    break

                if track[user] > 0:
                    counter += 1
                    users.append(f":{medal_dict[counter]}: {turnip_logo} {track[user]} - <@{user}>")
            lead_emb.add_field(name=key, value="\n".join(users))

        lead_emb.add_field(name="\u200b", value="\u200b")

        magic_money = total_earned - total_spend  # money that (dis)appeared of the economy
        if magic_money < 0:
            magic_msg = f"{abs(magic_money)} retiré de l'économie"
        else:
            magic_msg = f"{magic_money} ajouté à l'économie"

        lead_emb.add_field(name="Total", inline=False,
                           value=f"- {turnip_logo} {total_bought} achetés pour {currency_logo} {total_spend} coins\n"
                                 f"- {turnip_logo} {total_sold} vendus pour {currency_logo} {total_earned} coins\n"
                                 f"- {currency_logo} {magic_msg}")
        lead_emb.set_footer(text=f"『Recap』     『TyranBot』•『{get_parameter('version')}』")

        # Getting the channel to send the official leaderboard of the week
        lb_br_channel = self.bot.get_channel(lb_channel)
        await lb_br_channel.send(f"<@{lb_role}>", embed=lead_emb)

        # reset de la table
        curC.execute(f"UPDATE turnip SET turnipBought=0, turnipSold=0, coinsFromTurnip=0, coinsIntoTurnip=0")
        self.bot.log_action(f"[TURNIP] SQL Table reset", self.bot.turnip_logger)
        db.commit()

    def new_pattern(self, previous: str, patterns_chances: dict):
        self.bot.log_action(f"[TURNIP] Choosing pattern", self.bot.turnip_logger)

        if not previous:
            pattern = "3"

        else:
            chances_dict = patterns_chances[previous]
            chances = [[value, key] for key, value in chances_dict.items()]
            val = randint(1, 100)

            percentage_accept = 0
            for chance in chances:
                percentage_accept += chance[0]
                if val <= percentage_accept:
                    pattern = chance[1]
                    break
            else:
                self.bot.log_action(f"[TURNIP] Turnip file format invalid. Please correct the issue before restarting the bot.", self.bot.turnip_logger, 50)
                raise TurnipFileError

        return pattern

    def phases_duration(self, pattern: str):
        self.bot.log_action(f"[TURNIP] Determining phases durations", self.bot.turnip_logger)

        if pattern == "0":
            phase_1 = randint(0, 6)
            phase_2 = randint(2, 3)
            phase_3 = 7 - phase_1
            phase_4 = 5 - phase_2
            phase_5 = 3 - phase_3 if 3 - phase_3 > 0 else 0
            durations = [phase_1, phase_2, phase_3, phase_4, phase_5]

        elif pattern == "1":
            phase_1 = randint(1, 7)
            phase_2 = 3
            phase_3 = 2
            phase_4 = 7 - phase_1
            durations = [phase_1, phase_2, phase_3, phase_4]

        elif pattern == "2":
            durations = []

        elif pattern == "3":
            phase_1 = randint(0, 7)
            phase_2 = 5
            phase_3 = 12 - phase_1 - phase_2
            durations = [phase_1, phase_2, phase_3]

        else:
            self.bot.log_action(f"[TURNIP] Invalid pattern integer", self.bot.turnip_logger, 50)
            raise TurnipPatternError

        return durations

    def phases_prices(self, pattern: str, durations: list):
        self.bot.log_action(f"[TURNIP] Determining phases prices", self.bot.turnip_logger)

        base_price = randint(90, 110)
        self.buy_price = base_price

        if pattern == "0":
            phase_1 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[0])]
            base_rate_2 = randint(60, 80)
            phase_2 = []
            for _ in range(durations[1]):
                phase_2.append(round(base_price * base_rate_2 / 100))
                base_rate_2 -= randint(4, 10)
            phase_3 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[2])]
            base_rate_4 = randint(60, 80)
            phase_4 = []
            for _ in range(durations[3]):
                phase_4.append(round(base_price * base_rate_4 / 100))
                base_rate_4 -= randint(4, 10)
            phase_5 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[4])]

            prices = phase_1 + phase_2 + phase_3 + phase_4 + phase_5

        elif pattern == "1":
            base_rate_1 = randint(85, 90)
            phase_1 = []
            for _ in range(durations[0]):
                phase_1.append(round(base_price * base_rate_1 / 100))
                base_rate_1 -= randint(3, 5)
            phase_2 = [
                round(base_price * randint(90, 140) / 100),
                round(base_price * randint(140, 200) / 100),
                round(base_price * randint(200, 600) / 100)
            ]
            phase_3 = [round(base_price * randint(140, 200) / 100),
                       round(base_price * randint(90, 140) / 100)]
            phase_4 = [round(base_price * randint(40, 90) / 100) for _ in range(durations[3])]
            prices = phase_1 + phase_2 + phase_3 + phase_4

        elif pattern == "2":
            base_rate = randint(85, 90)
            prices = []
            for i in range(12):
                prices.append(round(base_price * base_rate / 100))
                base_rate -= randint(3, 5)

        elif pattern == "3":
            phase_1 = [round(base_price * (randint(40, 90) - i * randint(3, 5)) / 100) for i in
                       range(durations[0])]
            max_rate = randint(140, 200)
            phase_2 = [
                round(base_price * randint(90, 140) / 100),
                round(base_price * randint(90, 140) / 100),
                round(base_price * randint(min(140, max_rate - 1), max(140, max_rate - 1)) / 100),
                round(base_price * max_rate / 100),
                round(base_price * randint(min(140, max_rate - 1), max(140, max_rate - 1)) / 100)
            ]
            phase_3 = [round(base_price * (randint(40, 90) - i * randint(3, 5)) / 100) for i in
                       range(durations[2])]
            prices = phase_1 + phase_2 + phase_3

        else:
            self.bot.log_action(f"[TURNIP] Invalid pattern integer", self.bot.turnip_logger, 50)
            raise TurnipPatternError

        final_prices = [base_price] * 2 + prices

        return base_price, final_prices

    ############################################
    #                 Commands                 #
    ############################################

    turnip_group = SlashCommandGroup("turnip", "commands related to turnip")

    @turnip_group.command(name="debug")
    @option(name="count")
    @commands.is_owner()
    async def turnip_debug(self, ctx: ApplicationContext):
        await ctx.defer()

        self.bot.log_action(f"[TURNIP] Starting new week reset. (forced)", self.bot.turnip_logger)
        await self.new_week(round(time_now().timestamp()))
        self.bot.log_action(f"[TURNIP] New week reset finished.", self.bot.turnip_logger)

        await ctx.respond(f"EoC", ephemeral=True)

    @turnip_group.command(name="info")
    async def turnip_info(self, ctx: ApplicationContext):
        currency_logo, bot_version, turnip_logo = get_parameter(['currency-logo', 'version', 'turnip-emote'])

        curA.execute(f"SELECT turnipBought, turnipSold FROM turnip WHERE discordID = {ctx.author.id}")
        rowA = curA.fetchone()
        turnip_bought = rowA[0]
        turnip_sold = rowA[1]

        if self.can_buy:
            end_buy_phase = self.week_started_timestamp + 24 * 3600 - 1
            emb = Embed(color=0xfaf6e8,
                        description=f"Vous pouvez actuellement __**acheter**__ des navets et ce jusqu'au <t:{end_buy_phase}>\n\n"
                                    f"**Prix d'achat :** {currency_logo} {self.buy_price}"
                                    f"\n\nVous avez {turnip_logo} {turnip_bought - turnip_sold}.")

        else:
            end_week = self.week_started_timestamp + 7 * 24 * 3600 - 1
            emb = Embed(color=0xfaf6e8,
                        description=f"Vous pouvez actuellement __**vendre**__ des navets et ce jusqu'au <t:{end_week}>\n"
                                    f"Prochain changement: <t:{self.time_end_hd}:R>\n\n"
                                    f"**Prix de base :** {currency_logo} {self.buy_price}\n"
                                    f"**Prix de vente :** {currency_logo} {self.sell_price}"
                                    f"\n\nVous avez {turnip_logo} {turnip_bought - turnip_sold}")

        emb.set_author(name="Marché du navet",
                       icon_url="https://cdn.discordapp.com/emojis/1123000566969274508.webp?size=96&quality=lossless")
        emb.set_footer(text=f"『Marché du navet』     『TyranBot』•『{bot_version}』")
        await ctx.respond(embed=emb)

#
    @turnip_group.command(name="buy")
    async def turnip_buy(self, ctx: ApplicationContext, amt: int):
        await new_player(ctx.author)

        if not self.can_buy:
            raise CantBuyTurnip

        user = ctx.author
        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        coins = rowA[0]
        user_lang = rowA[1]
        price = amt * self.buy_price
        if coins < price:
            raise NotEnoughMoney
        else:
            currency_logo, turnip_logo = get_parameter(['currency-logo', 'turnip-emote'])

            curB.execute(f"UPDATE users SET coins = coins - {price} WHERE discordID = {user.id}")
            curC.execute(f"UPDATE turnip SET turnipBought=turnipBought+{amt}, coinsIntoTurnip=coinsIntoTurnip+{price} "
                         f"WHERE discordID = {user.id}")
            db.commit()
            # await ctx.respond(get_test("turnip.buy.success", user_lang))
            await ctx.respond(f"<:yes_tick:1123329478517596251> Successfully bought {turnip_logo} **{amt}** for {currency_logo} **{price}**")
            self.bot.log_action(f"[TURNIP] {user} bought {amt} turnip for {price} coins", self.bot.turnip_logger)

    @turnip_group.command(name="sell", usage="[turnip_amount: int]")
    async def turnip_sell(self, ctx: ApplicationContext, amt: int):
        await new_player(ctx.author)

        if not self.can_sell:
            raise CantSellTurnip

        user = ctx.author
        curA.execute(f"SELECT p.turnipBought, p.turnipSold, u.language FROM turnip as p, users as u "
                     f"WHERE p.discordID = {user.id} AND u.discordID = {user.id}")
        rowA = curA.fetchone()
        turnip_possessed = rowA[0] - rowA[1]
        user_lang = rowA[2]

        if turnip_possessed <= 0:
            await ctx.respond(get_text("turnip.sell.nothing_to_sell", user_lang))
            return

        amt = min(amt, turnip_possessed)

        currency_logo, turnip_logo = get_parameter(['currency-logo', 'turnip-emote'])
        earnings = amt * self.sell_price
        curB.execute(
            f"UPDATE turnip SET turnipSold= turnipSold + {amt}, coinsFromTurnip= coinsFromTurnip + {earnings} "
            f"WHERE discordID = {user.id}")
        curC.execute(f"UPDATE users SET coins= coins + {earnings} WHERE discordID= {user.id}")
        db.commit()

        # await ctx.respond(get_test("turnip.sell.success", user_lang))
        await ctx.respond(f"<:yes_tick:1123329478517596251> Successfully sold {turnip_logo} **{amt}** for {currency_logo} **{earnings}**")
        self.bot.log_action(f"[TURNIP] {user} sold {amt} turnip for {earnings} coins", self.bot.turnip_logger)


def setup(bot_):
    bot_.add_cog(Economy(bot_))
    bot_.add_cog(Turnip(bot_))
