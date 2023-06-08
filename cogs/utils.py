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

    @commands.slash_command(name="redeem")
    async def redeem(self, ctx: ApplicationContext, code: str):
        with open("json/codes.json", "r", encoding="utf-8") as code_file:
            codes = json.load(code_file)

        if code not in codes:
            raise UnknownCode

        user = ctx.author

        code_data = codes[code]
        effect = code_data['effect']
        extra = code_data['extra']
        usage_limit = code_data['usage_limit']
        usage_count = code_data['usage_count']

        if not (usage_count < usage_limit or usage_limit == -1):
            raise CodeLimitReached

        if effect == "money":
            curA.execute(f"UPDATE users SET coins = coins + {extra} WHERE discordID = {user.id}")
            db.commit()
            emb = Embed(color=Color.green(), description=f"You successfully redeemed the code `{code}`.\n"
                                                         f"You received {extra} coins.")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
            await ctx.respond(embed=emb, ephemeral=True)

        elif effect == "DM":
            try:
                await user.send(extra)
                emb = Embed(color=Color.green(), description=f"You successfully redeemed the code `{code}`.")
                emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
                await ctx.respond(embed=emb, ephemeral=True)
            except Forbidden:
                await ctx.respond(extra, ephemeral=True)

        elif effect == "role":
            guild = self.bot.get_guild(extra[0])
            role = guild.get_role(extra[1])
            member = guild.get_member(user.id)

            emb = Embed(color=Color.green(), description=f"You successfully redeemed the code `{code}`.\n"
                                                         f"You received the role {role.mention}")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")

            await member.add_roles(role)
            await ctx.respond(embed=emb, ephemeral=True)

        elif effect == "ping":
            channel = self.bot.get_channel(extra[0])
            emb = Embed(color=Color.dark_teal(), description=f"{user.mention} {extra[1]}")
            emb.set_footer(text=f"Code • {code}")
            await channel.send("@everyone", embed=emb)

            emb = Embed(color=Color.green(), description=f"You successfully redeemed the code `{code}`.\n"
                                                         f"**You {extra[1]}.**")
            emb.set_footer(text=f"『Redeem』     『TyranBot』•『{get_parameter('version')}』")
            await ctx.respond(embed=emb, ephemeral=True)

        else:
            raise UnexpectedError

        codes[code]['usage_count'] += 1
        with open("json/codes.json", "w", encoding="utf-8") as code_file:
            json.dump(codes, code_file, indent=2)

        await ctx.respond("end of command", ephemeral=True)


def setup(bot_):
    bot_.add_cog(Utils(bot_))
