from discord import Embed, Color, SlashCommandGroup
from discord.ext import commands, tasks

import json
from random import randint
from datetime import datetime, date

from main import db, new_player, get_parameter, time_now, key_with_lowest_value, sort_dict_by_value, get_text
from custom_errors import NotEnoughMoney

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)


def new_pattern():
    with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
        data = json.load(turnip_file)
        previous = data['last-pattern']
        patterns_chances = data['patterns-chances']

    if not previous:
        pattern = 3
    else:
        chances_dict = patterns_chances[previous]
        chances = [[value, key] for key, value in zip(chances_dict.keys(), chances_dict.values())]
        val = randint(1, 100)

        percentage_accept = 0
        for chance in chances:
            percentage_accept += chance[0]
            if val <= percentage_accept:
                pattern = chance[1]
                break
        else:
            print("PercentageError: check pattern chances")
            raise BaseException

    with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
        data['pattern'] = pattern
        json.dump(data, turnip_file, indent=2)


def phases_duration():
    with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
        data = json.load(turnip_file)
        pattern = data['pattern']

    if pattern == 0:
        phase_1 = randint(0, 6)
        phase_2 = randint(2, 3)
        phase_3 = 7 - phase_1
        phase_4 = 5 - phase_2
        phase_5 = 3 - phase_3 if 3 - phase_3 > 0 else 0
        durations = [phase_1, phase_2, phase_3, phase_4, phase_5]

    elif pattern == 1:
        phase_1 = randint(1, 7)
        phase_2 = 3
        phase_3 = 2
        phase_4 = 7 - phase_1
        durations = [phase_1, phase_2, phase_3, phase_4]

    elif pattern == 2:
        durations = []

    elif pattern == 3:
        phase_1 = randint(0, 7)
        phase_2 = 5
        phase_3 = 12 - phase_1 - phase_2
        durations = [phase_1, phase_2, phase_3]

    else:
        print("Invalid pattern value")
        raise ValueError

    with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
        data['durations'] = durations
        json.dump(data, turnip_file, indent=2)


def phases_prices():
    with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
        data = json.load(turnip_file)
        pattern = data['pattern']
        base_price = data['base-price']
        durations = data['durations']

    if pattern == 0:
        phase_1 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[0])]
        base_rate_2 = randint(60, 80)
        phase_2 = [round(base_price * (base_rate_2 - i * randint(4, 10) / 100)) for i in
                   range(durations[1])]
        phase_3 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[2])]
        base_rate_4 = randint(60, 80)
        phase_4 = [round(base_price * (base_rate_4 - i * randint(4, 10) / 100)) for i in
                   range(durations[3])]
        phase_5 = [round(base_price * randint(90, 140) / 100) for _ in range(durations[4])]

        prices = phase_1 + phase_2 + phase_3 + phase_4 + phase_5

    elif pattern == 1:
        base_rate_1 = randint(85, 90)
        phase_1 = [round(base_price * base_rate_1 - i * randint(3, 5) / 100) for i in
                   range(durations[0])]
        phase_2 = [
            round(base_price * randint(90, 140) / 100),
            round(base_price * randint(140, 200) / 100),
            round(base_price * randint(200, 600) / 100)
        ]
        phase_3 = [round(base_price * randint(140, 200) / 100),
                   round(base_price * randint(90, 140) / 100)]
        phase_4 = [round(base_price * randint(40, 90) / 100) for _ in range(durations[3])]
        prices = phase_1 + phase_2 + phase_3 + phase_4

    elif pattern == 2:
        base_rate = randint(85, 90)
        prices = []
        for i in range(11):
            prices.append(round(base_price * base_rate / 100))
            base_rate -= randint(3, 5)

    elif pattern == 3:
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
        print("Invalid pattern value")
        raise ValueError

    with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
        data['prices'] = [base_price]*2 + prices
        json.dump(data, turnip_file, indent=2)


class TurnipCog(commands.Cog):
    """
        Fonctions liées au cours du navet
        based on :
        https://docs.google.com/document/d/1bSVNpOnH_dKxkAGr718-iqh8s8Z0qQ54L-0mD-lbrXo/edit#heading=h.plkfxg2erbyb
    """

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log_msg = "[COG] 'TurnipCog' has been loaded"
        self.client.log_action(txt=log_msg)

    @tasks.loop(seconds=30)
    async def turnip_loop(self):
        now_timestamp = time_now()

        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)

        week_started = data['week-started']
        week_started_timestamp = round(datetime.strptime(week_started, "%Y-%m-%d").timestamp())

        half_day = data["half-day"] + 1
        time_end_hd = week_started_timestamp + half_day * 3600 * 12

        today = date.today().strftime("%a")

        # on compare les temps pour savoir si on a changé de demi-journée
        if now_timestamp > time_end_hd:

            # check if it has been 7 days or more since last update
            if now_timestamp - week_started_timestamp >= 3600 * 24 * 7:
                if today == 'Sun':
                    await self.new_week()
                    pass
                else:
                    data['can-buy'] = False
                    data['can-sell'] = False

            elif today == 'Sun':  # si on est dimanche et que ça fait moins d'une semaine rien à faire
                pass

            else:  # si on n'est pas dimanche on fait les modifications nécessaires
                half_day = int((now_timestamp - week_started_timestamp) // (3600*12))
                print(half_day)
                data["half-day"] = half_day
                data['active-price'] = data['prices'][half_day]

            with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
                json.dump(data, turnip_file, indent=2)

    async def new_week(self):
        """
        Save data from table 'turnip' into a json file and send it (somewhere) before resetting the table.
        Also make recaps per user and a leaderboard
        :return:

        TOD :
            - envoyer les logs de la table sur un repo
            https://stackoverflow.com/questions/40741581/create-file-in-github-repository-with-pygithub
        """
        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            turnip_settings = json.load(turnip_file)
            start_date = turnip_settings['week-started']

        currency_logo = get_parameter('currency-logo')

        highest_lost = {"id": -1, "id2": -1, "id3": -1}
        most_rotten = {"id": -1, "id2": -1, "id3": -1}
        most_bought = {"id": -1, "id2": -1, "id3": -1}

        selected_data = ["discordID", "turnipBought", "turnipSold", "coinsFromTurnip", "coinsIntoTurnip", "recap"]
        curA.execute(f"SELECT {', '.join(selected_data)} FROM turnip WHERE turnipBought > 0")
        rowsA = curA.fetchall()

        with open(f"logs/turnip/{start_date}.json", 'w', encoding='utf-8') as turnip_log_file:
            logs = {}

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

                if recap and user_id == 444504367152889877:
                    recap_emb = Embed(color=Color.magenta())

                    recap_emb.add_field(name="Achats",
                                        value=f"{turnip_bought} 🥔 \n{expenses} {currency_logo} dépensés")
                    recap_emb.add_field(name="Vente", value=f"{turnip_sold} 🥔 \n{earnings} {currency_logo} obtenus")

                    if loss < 0:
                        msg = f"{loss} {currency_logo} perdus"
                    elif expenses == earnings:
                        msg = "Autant d'argent dépensé qu'obtenu"
                    else:
                        msg = f"{earnings - expenses} {currency_logo} obtenus"

                    recap_emb.add_field(name="Total", value=f"{rotten} 🥔 perdues {'(bravo!)' if rotten == 0 else ''}"
                                                            f"\n{msg}")

                    recap_emb.set_footer(text=f"『Recap』     『 TyranBot 』•『{get_parameter('version')}』")

                    user = self.client.get_user(user_id)
                    user.send("Voici ton récapitulatif de la semaine", embed=recap_emb)

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
            "Most money lost": highest_lost, "Most turnipes rotten": most_rotten, "Most turnipes lost": most_bought
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
        magic_money = total_earned - total_spend
        if magic_money < 0:
            extra_msg += f"{abs(magic_money)} {currency_logo} retiré de l'économie"
        elif magic_money > 0:
            extra_msg += f"{magic_money} {currency_logo} ajouté à l'économie"
        lead_emb.add_field(name="Extra", value=f"{total_bought - total_sold} 🥔 pourries \n{extra_msg} ")

        lb_br_channel = self.client.get_channel(get_parameter('turnip-leaderboard-channel'))
        await lb_br_channel.send(f"<@{get_parameter('turnip-leaderboard-role')}>", embed=lead_emb)

        # reset de la table
        curC.execute(f"UPDATE turnip SET turnipBought=0, turnipSold=0, coinsFromTurnip=0, coinsIntoTurnip=0")
        print("table reset")
        db.commit()

        # updating the last pattern
        with open("json/turnip.json", 'w', encoding='utf-8') as turnip_file:
            turnip_settings['last-pattern'] = turnip_settings['pattern']
            json.dump(turnip_settings, turnip_file, indent=2)

        # generating new values for the new week
        new_pattern()
        phases_duration()
        phases_prices()

    #

    turnip_group = SlashCommandGroup("turnip", "commands related to turnip")

    @turnip_group.command(name="info")
    async def turnip_info(self, ctx):
        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)
            start_time = int(datetime.strptime(data['week-started'], "%Y-%m-%d").timestamp())
            base_price = data['base-price']
            active_price = data['active-price']

        day = date.today().strftime("%a")
        emb = Embed(color=Color.teal(), title="🥔 turnip market 🥔")

        if day == 'Sun':
            end_time = start_time + 3600*24
            emb.add_field(name="Turnip buy price", value=f"{base_price} {get_parameter('currency-logo')}")
            emb.add_field(name="Time left to buy", value=f"<t:{end_time}:R>")

        else:
            end_time = start_time + 3600*24*7
            emb.add_field(name="Turnip sell price :", value=f"{active_price} {get_parameter('currency-logo')}")
            emb.add_field(name="Time left to sell", value=f"<t:{end_time}:R>")

        emb.set_footer(text=f"『Market info』     『 TyranBot 』•『{get_parameter('version')}』")
        await ctx.respond(embed=emb)

#
    @turnip_group.command(name="buy")
    async def turnip_buy(self, ctx, amt: int):
        await new_player(ctx.author)
        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)
            can_buy = data['can-buy']
            base_price = data['base-price']

        if not can_buy:
            # todo: raise custom error
            await ctx.respond("You can't buy turnip now", ephemeral=True)

        else:
            user = ctx.author
            curA.execute(f"SELECT coins, language FROM users WHERE discordID = {user.id}")
            rowA = curA.fetchone()
            coins = rowA[0]
            user_lang = rowA[1]
            price = amt * base_price
            if coins < price:
                raise NotEnoughMoney
            else:
                curB.execute(f"UPDATE users SET coins = coins - {price} WHERE discordID = {user.id}")
                curC.execute(
                    f"UPDATE turnip SET turnipBought=turnipBought+{amt}, coinsIntoTurnip=coinsIntoTurnip+{price} "
                    f"WHERE discordID = {user.id}")
                db.commit()
                # await ctx.respond(get_test("turnip.buy.success", user_lang))  # "lang
                await ctx.respond(f"Successfully bought {amt} turnip for {price} {get_parameter('currency-logo')}")

    @turnip_group.command(name="sell", usage="[turnip_amount: int]")
    async def turnip_sell(self, ctx, amt: int):
        await new_player(ctx.author)
        with open("json/turnip.json", 'r', encoding='utf-8') as turnip_file:
            data = json.load(turnip_file)
            can_sell = data['can-sell']
            active_price = data['active-price']

        if not can_sell:
            # todo: raise custom error
            await ctx.respond("You can't sell turnip now", ephemeral=True)
            return

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

        earnings = amt * active_price
        curB.execute(
            f"UPDATE turnip SET turnipSold= turnipSold + {amt}, coinsFromTurnip= coinsFromTurnip + {earnings} "
            f"WHERE discordID = {user.id}")
        curC.execute(f"UPDATE users SET coins= coins + {earnings} WHERE discordID= {user.id}")
        db.commit()

        # await ctx.respond(get_test("turnip.sell.success", user_lang))  # "lang
        await ctx.respond(f"Successfully sold {amt} turnipes for {earnings}")


def setup(client):
    client.add_cog(TurnipCog(client))
