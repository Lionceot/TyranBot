import discord
from discord import Embed, Color, User, ApplicationContext, Message, SlashCommandGroup, AutocompleteContext, \
    OptionChoice
from discord.ext import commands, tasks
from discord.utils import get
from discord.commands import option
from discord.ui import view, button, select

import json
import random
import asyncio
from dotenv import load_dotenv

from main import db, in_database, new_player, get_parameter, MyBot, time_now, get_text
from custom_errors import NotEnoughMoney, IncorrectBetValue, UnknownSign, UserIsBot, UnknownObject, MaxAmountReached, \
    HowDidYouGetHere
from custom_views import PaymentView, ShopBrowserView

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
    curA.execute(f"SELECT multiplier FROM active_boosts WHERE discordID = {user.id} and boostType = {boost_type} "
                 f"ORDER BY multiplier DESC LIMIT 1")
    rowA = curA.fetchone()
    if rowA is not None:
        return rowA[0]
    return 1


class EconomyCog(commands.Cog):
    """
        Toutes les commandes liées au système économique
    """

    def __init__(self, bot_: MyBot):
        self.bot = bot_
        self.bet_limit = get_parameter('bet_limit')

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'EconomyCog' has been loaded"
        self.bot.log_action(txt=log_msg)

    @tasks.loop(seconds=1)
    async def daily_loop(self):
        now = time_now().strftime("%H:%M:%S")

        if now == "00:00:00":
            curA.execute("UPDATE dailyrecord SET streak = 0 WHERE claimed = 0")
            curB.execute("UPDATE dailyrecord SET ready = 1, claimed = 0")
            db.commit()

    @commands.slash_command(name="coins", description="Indique la quantité d'argent d'un utilisateur.",
                            brief="Show a user's amount of money")
    @commands.guild_only()
    async def coins(self, ctx: ApplicationContext, user: discord.User = None):
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

    @commands.slash_command(name="leaderboard", aliases=["lb", "richest"])
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
                user_name = await self.bot.fetch_user(user_id)
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
                user_name = await self.bot.fetch_user(user_id)
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
            em = Embed(color=Color.red(), description=get_text("daily.already_done", user_lang))  # "lang
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

        boost = get_parameter("global_boost") * get_boost(user, "coins")
        earnings = int(round(random.randint(50, 120) * streak_factor) * boost)
        nbDaily = min(7, row[2] + 1)

        curB.execute(
            f"UPDATE DailyRecord SET streak = {streak}, ready = 0, claimed = 1, nbDaily = {nbDaily}, "
            f"bestStreak = {max(streak, best_streak)} WHERE discordID = {user.id}")
        curC.execute(f"UPDATE Users SET coins = coins + {earnings} WHERE discordID = {user.id}")
        db.commit()

        currency_logo = get_parameter('currency-logo')

        response_text = get_text("daily.claim", user_lang)  # "lang
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
            # response_text.replace("%nbDaily%", nbDaily) "lang
            await ctx.respond(response_text, ephemeral=True)

        else:
            earnings = random.randint(50, 120) * get_parameter("global_boost") * get_boost(user, "coins")
            curB.execute(f"UPDATE users AS u, dailyrecord AS d SET u.coins = u.coins + {earnings}, d.nbDaily = 0 "
                         f"WHERE u.discordID = {user.id} and d.discordID = {user.id} ")
            db.commit()

            response_text = get_text("bonus.success", user_lang)
            # response_text = response_text.replace("%amount%", f"{earnings} {get_parameter('currency-logo')}") "lang
            await ctx.respond(response_text)

    @commands.slash_command(name="work", description="Récupérer votre salaire toutes les 3h.")
    @commands.guild_only()
    @commands.cooldown(1, 10800, commands.BucketType.user)
    async def work(self, ctx: ApplicationContext):
        user = ctx.author
        await new_player(user)

        earnings = random.randint(100, 200) * get_parameter("global_boost") * get_boost(user, "coins")
        curA.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
        db.commit()

        await ctx.respond(f"You worked and earned {earnings} {get_parameter('currency-logo')}")

    @commands.slash_command(name="shop", description="Show the available things to buy")
    @commands.guild_only()
    @option(name="category", description="What section are you looking for ?", choices=["ranks", "colors", "perks"])
    async def shop(self, ctx: ApplicationContext, category: str = "home"):  # "lang
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
        # "lang
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
    @commands.is_owner()  # todo: remove that
    async def use(self, ctx: ApplicationContext, item_id: str):
        user = ctx.author
        curA.execute(f"SELECT language FROM users WHERE discordID = {user.id}")

        user_lang = curA.fetchone()[0]
        user_inv = [item[0] for item in get_inventory(user)]

        if item_id not in user_inv:
            await ctx.respond(get_text("use.not_possessed", user_lang))  # "lang
            return

        curB.execute(f"SELECT amount, used FROM bag WHERE discordID = {user.id} AND objectID = '{item_id}'")
        rowB = curB.fetchone()
        amount = rowB[0]
        used = rowB[1]

        if used == 1:
            await ctx.respond(get_text("use.already_used", user_lang))  # "lang
            return

        curC.execute(f"SELECT objectType, extID FROM objects WHERE objectID = '{item_id}'")
        rowC = curC.fetchone()

        if rowC is None:
            await ctx.respond(get_text("use.unknown_object_in_inventory", user_lang))  # "lang
            self.bot.log_action(f"Un-handled objectID for item {item_id} in {user}s inventory", 40)
            return

        object_type = rowC[0]
        ext_id = rowC[1]

        if object_type == "role":
            guild = ctx.guild
            await user.add_roles(guild.get_role(ext_id), reason=f"Using object {item_id}")
            await ctx.respond(get_text("use.role_added", user_lang))  # "lang
            curD.execute(f"UPDATE bag SET used = 1 WHERE discordID = {user.id} AND objectID = '{item_id}'")
            db.commit()

        elif object_type == "ticket":
            # TODO: update when tickets will be available
            await ctx.respond(get_text("command.feature_not_added", user_lang))  # "lang

        elif object_type == "toggle":
            await ctx.respond(get_text("use.toggle", user_lang))  # "lang

        elif object_type == "dummy":
            await ctx.respond(get_text("use.no_use", user_lang))  # "lang

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
            await ctx.respond(get_text("use.boost_used", user_lang))  # "lang

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
            await ctx.respond(get_text("use.boost_used", user_lang))  # "lang

        else:
            await ctx.respond(get_text("use.unhandled_objectType", user_lang))  # "lang
            self.bot.log_action(f"Un-handled object type for item {item_id}", 40)

    @commands.slash_command(name="inventory", description="See someone's inventory")
    @option(name="user", description="Who do you want to see the inventory ?")
    async def inventory(self, ctx, user: discord.User = None):
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
    async def mc_inventory(self, ctx, message: discord.Message):
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
            # "lang
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

        await ctx.respond(get_text("dice.start", user_lang))  # "lang

        currency_logo = get_parameter('currency-logo')
        j1, j2 = random.randint(1, 6), random.randint(1, 6)

        if j1 + j2 == 12:
            earnings = bet * 3 * get_parameter("global_boost") * get_boost(user, "coins")
            text_1 = get_text("dice.double_6.part_1", user_lang)
            text_2 = get_text("dice.double_6.part_2", user_lang)
            text_3 = get_text("dice.win", user_lang)

            curB.execute(
                f"UPDATE stats SET dicePlayed=dicePlayed+1, diceWon=diceWon+1, coinsBetInGames=coinsBetInGames+{bet}, coinsWonInGames=coinsWonInGames+{earnings} "
                f"WHERE discordID = {user.id}")

        else:
            b1, b2 = random.randint(1, 6), random.randint(1, 6)

            text_1 = get_text("dice.regular.part_1", user_lang)
            text_2 = get_text("dice.regular.part_2", user_lang)

            if j1 + j2 < b1 + b2:
                text_3 = get_text("dice.lose", user_lang)
                earnings = -bet
                curB.execute(f"UPDATE stats SET dicePlayed=dicePlayed+1, coinsBetInGames=coinsBetInGames+{bet}, "
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID = {user.id}")

            elif j1 + j2 > b1 + b2:
                if j1 == j2:
                    earnings = bet * 2 * get_parameter("global_boost") * get_boost(user, "coins")
                else:
                    earnings = bet * get_parameter("global_boost") * get_boost(user, "coins")

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

        goal = random.randint(1, 100)
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
                await ctx.send(get_text("guess.lost", user_lang))  # "lang
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

                await ctx.send(get_text("guess.win", user_lang))  # "lang

                curB.execute(f"UPDATE users SET coins = coins+{reward} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET guessPlayed=guessPlayed+1, guessWon=guessWon+1, "
                             f"coinsBetInGames=coinsInGames+{bet}, coinsWonInGames=coinsWonInGames+{reward} "
                             f"WHERE discordID={user.id}")

        else:
            if lost:
                await ctx.send(get_text("guess.no_bet.lost", user_lang))  # "lang
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
    # @commands.cooldown(1, 3600, commands.BucketType.user)  # todo: cooldown
    async def coinflip(self, ctx: ApplicationContext, side: str, bet: int = None):
        user = ctx.author
        await new_player(user)

        curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
        rowA = curA.fetchone()
        user_coins = rowA[0]
        user_lang = rowA[1]
        result = random.choice(["head", "tail"])

        await ctx.respond(get_text("coinflip.start", user_lang))
        await asyncio.sleep(1.5)
        await ctx.send(get_text("coinflip.result", user_lang))  # "lang
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
                earnings = bet * get_parameter('global_boost') * get_boost(user, "coins")
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
    # @commands.cooldown(1, 3600, commands.BucketType.user)  # todo: cooldown
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

        bot_sign = random.choice(["rock", "paper", "scissors"])
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

        await ctx.respond(get_text("rps.player_play", user_lang))  # "lang
        await asyncio.sleep(1.5)
        await ctx.send(get_text("rps.bot_play", user_lang))  # "lang
        await asyncio.sleep(1.5)

        if bet:
            if score == 0:
                curB.execute(f"UPDATE users SET coins = coins - {bet} WHERE discordID = {user.id}")
                curC.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, coinsBetInGames=coinsBetInGames+{bet}, "
                             f"coinsLostInGames=coinsLostInGames+{bet} WHERE discordID={user.id}")
                await ctx.send(get_text("rps.lose", user_lang))  # "lang
            elif score == 1:
                earnings = bet * get_parameter("global_boost") * get_boost(user, "coins")
                curB.execute(f"UPDATE users SET coins = coins + {earnings} WHERE discordID = {user.id}")
                curC.execute(
                    f"UPDATE stats SET rpsPlayed=rpsPlayed+1, rpsWon=rpsWon+1, coinsBetInGames=coinsBetInGames+{bet},"
                    f"coinsWonInGames=coinsWonInGames+{earnings} WHERE discordID={user.id}")
                await ctx.send(get_text("rps.win", user_lang))  # "lang
            else:
                curC.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, coinsBetInGames=coinsBetInGames+{bet} "
                             f"WHERE discordID={user.id}")
                await ctx.send(get_text("rps.draw", user_lang))  # "lang

        else:
            if score == 0:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.lose", user_lang))  # "lang
            elif score == 1:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1, rpsWon=rpsWon+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.win", user_lang))  # "lang
            else:
                curB.execute(f"UPDATE stats SET rpsPlayed=rpsPlayed+1 WHERE discordID={user.id}")
                await ctx.send(get_text("rps.no_bet.draw", user_lang))  # "lang
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
        statEmb.set_author(name=f"{user}'s stats")
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

    @commands.message_command(name="Author's stats")
    async def mc_stats(self, ctx: ApplicationContext, message: Message):
        user = message.author
        if user.bot:
            raise UserIsBot(user=user)

        if not in_database(user):
            await ctx.respond(get_text("stats.no_stat", ""), ephemeral=True)
        statEmb = self.get_stat_emb(user)
        await ctx.respond(embed=statEmb)

    @commands.user_command(name="User's stats")
    async def uc_stats(self, ctx: ApplicationContext, user: User):
        if user.bot:
            raise UserIsBot(user=user)

        if not in_database(user):
            await ctx.respond(get_text("stats.no_stat", ""), ephemeral=True)
        statEmb = self.get_stat_emb(user)
        await ctx.respond(embed=statEmb)


def setup(bot_):
    bot_.add_cog(EconomyCog(bot_))
