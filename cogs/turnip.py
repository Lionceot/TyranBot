from discord import Embed, Color, SlashCommandGroup, ApplicationContext
from discord.ext import commands, tasks
from discord.commands import option

import json
from random import randint
from datetime import datetime, date

from main import db, new_player, get_parameter, time_now, key_with_lowest_value, sort_dict_by_value, get_text, MyBot
from custom_errors import NotEnoughMoney, TurnipFileError, TurnipPatternError, CantBuyTurnip, CantSellTurnip

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)


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
        self.time_end_hd = self.week_started_timestamp + self.half_day * 3600 * 12

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
        currency_logo, bot_version, lb_role, lb_channel = get_parameter(
            ['currency-logo', 'version', 'turnip-leaderboard-role', 'turnip-leaderboard-channel']
        )

        # Querying data from the DB
        selected_data = ["discordID", "turnipBought", "turnipSold", "coinsFromTurnip", "coinsIntoTurnip", "recap"]
        curA.execute(f"SELECT {', '.join(selected_data)} FROM turnip WHERE turnipBought > 0")
        rowsA = curA.fetchall()

        # Creating new file to save the week's data
        logs = {}

        # Leaderboard categories
        highest_lost = {"id": -1, "id2": -1, "id3": -1}
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
                recap_emb = Embed(color=Color.magenta())

                recap_emb.add_field(name="Achats",
                                    value=f"{turnip_bought} 🥔 \n{expenses} {currency_logo} dépensés")
                recap_emb.add_field(name="Vente", value=f"{turnip_sold} 🥔 \n{earnings} {currency_logo} obtenus")

                if earnings < expenses:
                    msg = f"{abs(earnings - expenses)} {currency_logo} perdus"
                elif expenses == earnings:
                    msg = "Autant d'argent dépensé qu'obtenu"
                else:
                    msg = f"{earnings - expenses} {currency_logo} obtenus"

                recap_emb.add_field(name="Total", value=f"{rotten} 🥔 perdues {'(bravo!)' if rotten == 0 else ''}"
                                                        f"\n{msg}")

                recap_emb.set_footer(text=f"『Recap』     『 TyranBot 』•『{bot_version}』")

                user = self.bot.get_user(user_id)
                await user.send("Voici ton récapitulatif de la semaine", embed=recap_emb)

            lowest_track = key_with_lowest_value(highest_lost)
            if highest_lost[lowest_track] < loss:
                del highest_lost[lowest_track]
                highest_lost[user_id] = loss

            lowest_track = key_with_lowest_value(most_rotten)
            if most_rotten[lowest_track] < rotten:
                del most_rotten[lowest_track]
                most_rotten[user_id] = rotten

            lowest_track = key_with_lowest_value(most_bought)
            if most_bought[lowest_track] < turnip_bought:
                del most_bought[lowest_track]
                most_bought[user_id] = turnip_bought

        with open(f"logs/turnip/{start_date}.json", 'w', encoding='utf-8') as turnip_log_file:
            json.dump(logs, turnip_log_file, indent=2)

        curB.execute(f"SELECT sum(turnipBought),sum(turnipSold),sum(coinsFromTurnip),sum(coinsIntoTurnip) FROM turnip")
        rowB = curB.fetchone()
        total_bought = rowB[0]
        total_sold = rowB[1]
        total_earned = rowB[2]
        total_spend = rowB[3]

        lead_emb = Embed(color=Color.dark_teal(),
                         title=f"Résumé de la semaine du {'/'.join(reversed(start_date.split('-')))}",
                         description=f"Un total de {total_bought} patates achetées pour {total_spend} {currency_logo}"
                                     f" et {total_sold} vendues pour {total_earned} {currency_logo}")

        leaderboards = {
            "Most money lost": highest_lost, "Most turnips rotten": most_rotten, "Most turnips bought": most_bought
        }

        for key in leaderboards:
            users = []
            track = sort_dict_by_value(leaderboards[key], True)
            medal_dict = {1: "first_place", 2: "second_place", 3: "third_place"}
            counter = 0
            for user in track:
                if track[user] > 0:
                    counter += 1
                    users.append(f":{medal_dict[counter]}: <@{user}> - {track[user]}")
            lead_emb.add_field(name=key, value="\n".join(users))

        extra_msg = ""
        magic_money = total_earned - total_spend  # money that (dis)appeared of the economy
        if magic_money < 0:
            extra_msg += f"{abs(magic_money)} {currency_logo} retiré de l'économie"
        elif magic_money > 0:
            extra_msg += f"{magic_money} {currency_logo} ajouté à l'économie"
        lead_emb.add_field(name="Extra", value=f"{total_bought - total_sold} 🥔 pourries \n{extra_msg} ")

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
            for i in range(11):
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
    async def turnip_debug(self, ctx: ApplicationContext):
        await ctx.defer()
        """with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            turnip_settings = json.load(turnip_file)

        for _ in range(count):
            pattern = self.new_pattern(turnip_settings['last-pattern'], turnip_settings['patterns-chances'])
            durations = self.phases_duration(pattern)
            base_price, final_prices = self.phases_prices(pattern, durations)
            with open("test_result.txt", "a", encoding="utf-8") as result_file:
                result_file.write(f"{pattern}, {base_price}, {final_prices}\n")

        await self.new_week(round(time_now().timestamp()))"""

        await ctx.respond(f"EoC", ephemeral=True)

    @turnip_group.command(name="info")
    async def turnip_info(self, ctx):
        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)
            start_time = int(datetime.strptime(data['week-started'], "%Y-%m-%d").timestamp())

        day = date.today().strftime("%a")
        emb = Embed(color=Color.teal(), title="🥔 turnip market 🥔")

        if day == 'Sun':
            end_time = start_time + 3600*24
            emb.add_field(name="Turnip buy price", value=f"{self.buy_price} {get_parameter('currency-logo')}")
            emb.add_field(name="Time left to buy", value=f"<t:{end_time}:R>")

        else:
            end_time = start_time + 3600*24*7
            emb.add_field(name="Turnip sell price :", value=f"{self.sell_price} {get_parameter('currency-logo')}")
            emb.add_field(name="Time left to sell", value=f"<t:{end_time}:R>")

        emb.set_footer(text=f"『Market info』     『 TyranBot 』•『{get_parameter('version')}』")
        await ctx.respond(embed=emb)

#
    @turnip_group.command(name="buy")
    async def turnip_buy(self, ctx, amt: int):
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
            curB.execute(f"UPDATE users SET coins = coins - {price} WHERE discordID = {user.id}")
            curC.execute(f"UPDATE turnip SET turnipBought=turnipBought+{amt}, coinsIntoTurnip=coinsIntoTurnip+{price} "
                         f"WHERE discordID = {user.id}")
            db.commit()
            # await ctx.respond(get_test("turnip.buy.success", user_lang))  
            await ctx.respond(f"Successfully bought {amt} turnip for {price} {get_parameter('currency-logo')}")

    @turnip_group.command(name="sell", usage="[turnip_amount: int]")
    async def turnip_sell(self, ctx, amt: int):
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

        earnings = amt * self.sell_price
        curB.execute(
            f"UPDATE turnip SET turnipSold= turnipSold + {amt}, coinsFromTurnip= coinsFromTurnip + {earnings} "
            f"WHERE discordID = {user.id}")
        curC.execute(f"UPDATE users SET coins= coins + {earnings} WHERE discordID= {user.id}")
        db.commit()

        # await ctx.respond(get_test("turnip.sell.success", user_lang))  # "lang
        await ctx.respond(f"Successfully sold {amt} turnips for {earnings}")


def setup(client):
    client.add_cog(Turnip(client))
