from discord import ButtonStyle, User, Interaction, Embed, Color, InputTextStyle
from discord.ui import View, Button, Modal, InputText

from json import dump as json_dump

from main import db, get_parameter, get_text
from custom_functions import get_codes_data

curA = db.cursor(buffered=True)
curB = db.cursor(buffered=True)
curC = db.cursor(buffered=True)


class PaymentConfirmButton(Button):
    def __init__(self, sender: User, receiver: User, amount: int, lang: str):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.user_lang = lang
        super().__init__(
            label=get_text("view.payment.accept", self.user_lang),
            style=ButtonStyle.green,
            custom_id="payment:confirm"
        )

    async def callback(self, interaction: Interaction):
        curA.execute(f"UPDATE users SET coins =  coins - {self.amount} WHERE discordID = {self.sender.id}")
        curB.execute(f"UPDATE users SET coins = coins + {self.amount} WHERE discordID = {self.receiver.id}")
        db.commit()
        response_text = get_text("pay.success", self.user_lang)  # "lang
        # response_text = response_text.replace("%amount%", f"{self.amount} {get_parameter('currency-logo')}")
        # response_text = response_text.replace("%receiver%", self.receiver.mention)
        await interaction.response.send_message(
            f"❱❱ {self.amount} {get_parameter('currency-logo')} were given to {self.receiver.mention}.")


class PaymentCancelButton(Button):
    def __init__(self, lang: str):
        self.user_lang = lang
        super().__init__(
            label=get_text("view.payment.cancel", self.user_lang),
            style=ButtonStyle.red,
            custom_id="payment:cancel"
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.send_message(get_text("pay.canceled", self.user_lang), ephemeral=True)


class PaymentView(View):
    def __init__(self, sender: User, receiver: User, amount: int, lang: str):
        super().__init__(
            timeout=30
        )
        self.add_item(PaymentConfirmButton(sender=sender, receiver=receiver, amount=amount, lang=lang))
        self.add_item(PaymentCancelButton(lang=lang))

    async def on_timeout(self):
        await self.message.edit(content="Timeout ! Operation canceled.", view=None)


# todo: both views below (auto-equip role/ticket)
class AutoEquipRole(View):
    pass


class AutoEquipTicket(View):
    pass


class DeleteShopItemView(View):
    def __init__(self, object_id: str, bot):
        super().__init__(
            timeout=30
        )
        self.add_item(DeleteShopItemConfirm(object_id=object_id, bot=bot))
        self.add_item(DeleteShopItemDeny())

    async def on_timeout(self):
        await self.message.edit(content="Timeout ! Operation canceled.", view=None)


class DeleteShopItemConfirm(Button):
    def __init__(self, object_id: str, bot):
        super().__init__(
            label=get_text("view.shop_item_deletion.confirm", ""),
            style=ButtonStyle.green,
            custom_id="shop_item_deletion:confirm"
        )
        self.object_id = object_id
        self.bot = bot

    async def callback(self, interaction: Interaction):
        curA.execute(f"DELETE FROM objects WHERE objectID = '{self.object_id}'")
        db.commit()
        self.bot.log_action(f"Item {self.object_id} deleted by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message("Item deleted !", ephemeral=True)
        self.bot.log_action(f"[ADMIN] Item '{self.object_id}' was removed from the shop", self.bot.eco_logger)
        await self.view.message.delete()


class DeleteShopItemDeny(Button):
    def __init__(self):
        super().__init__(
            label=get_text("view.shop_item_deletion.cancel", ""),
            style=ButtonStyle.red,
            custom_id="shop_item_deletion:cancel"
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.send_message("Operation canceled !", ephemeral=True)
        await self.view.message.delete()


class ShopBrowserView(View):
    def __init__(self, category: str, lang: str):
        super().__init__(
            timeout=None
        )

        self.add_item(ShopHomeButton(disabled=category == 'home', lang=lang))
        self.add_item(ShopRanksButton(disabled=category == 'ranks', lang=lang))
        self.add_item(ShopColorsButton(disabled=category == 'colors', lang=lang))
        self.add_item(ShopPerksButton(disabled=category == 'perks', lang=lang))

    async def on_timeout(self):
        pass


class ShopHomeButton(Button):
    def __init__(self, disabled: bool, lang: str):
        super().__init__(
            label=get_text("view.shop.home", ""),
            style=ButtonStyle.blurple,
            custom_id="shop:home",
            disabled=disabled
        )
        self.lang = lang

    async def callback(self, interaction: Interaction):
        emb = Embed(color=Color.dark_theme(), description=get_text("shop.home.desc", self.lang))\
            .set_author(name=get_text("shop.home.author", self.lang))\
            .set_footer(text=get_text("shop.footer", self.lang))

        await interaction.response.edit_message(embed=emb, view=ShopBrowserView(category='home', lang=self.lang))


class ShopRanksButton(Button):  #"lang
    def __init__(self, disabled: bool, lang: str):
        super().__init__(
            label=get_text("view.shop.ranks", ""),
            style=ButtonStyle.blurple,
            custom_id="shop:ranks_section",
            disabled=disabled
        )
        self.lang = lang

    async def callback(self, interaction: Interaction):
        curA.execute(f"SELECT objectID, price, need AS need_extID "
                     f"FROM objects WHERE category='ranks' AND locked=0 AND exclusive=0;")
        rowsA = curA.fetchall()

        curB.execute(f"SELECT objectID, price, need AS need_extID "
                     f"FROM objects WHERE category='ranks' AND locked=0 AND exclusive=1;")
        rowsB = curB.fetchall()

        emb = Embed(color=Color.dark_magenta(), description=get_text("shop.ranks.desc", self.lang))\
            .set_author(name=get_text("shop.title.ranks", self.lang))\
            .set_footer(text=get_text("shop.footer", self.lang))

        currency_logo = get_parameter('currency-logo')

        text = []
        for elt in rowsA:
            t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
            if elt[2] is not None:
                t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
            text.append(t)

        text = "\n".join(text)

        if len(rowsB) > 0:
            exclu_text = []
            for elt in rowsB:
                t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
                if elt[2] is not None:
                    t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
                exclu_text.append(t)

            exclu_text = "\n".join(exclu_text)
            emb.add_field(name=get_text("shop.exclusive_items", self.lang), value=exclu_text)

        emb.add_field(name=get_text("shop.global_items", self.lang), value=text, inline=False)

        await interaction.response.edit_message(embed=emb, view=ShopBrowserView(category='ranks', lang=self.lang))


class ShopColorsButton(Button):  #"lang
    def __init__(self, disabled: bool, lang: str):
        super().__init__(
            label=get_text("view.shop.colors", ""),
            style=ButtonStyle.blurple,
            custom_id="shop:colors_section",
            disabled=disabled
        )
        self.lang = lang

    async def callback(self, interaction: Interaction):
        curA.execute(f"SELECT objectID, price, need "
                     f"FROM objects WHERE category='colors' AND locked=0 AND exclusive=0;")
        rowsA = curA.fetchall()

        curB.execute(f"SELECT objectID, price, need AS need_extID "
                     f"FROM objects WHERE category='colors' AND locked=0 AND exclusive=1;")
        rowsB = curB.fetchall()

        emb = Embed(color=Color.orange(), description=get_text("shop.colors.desc", self.lang))\
            .set_author(name=get_text("shop.title.colors", self.lang))\
            .set_footer(text=get_text("shop.footer", self.lang))

        currency_logo = get_parameter('currency-logo')

        text = []
        for elt in rowsA:
            t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
            if elt[2] is not None:
                t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
            text.append(t)

        text = "\n".join(text)

        if len(rowsB) > 0:
            exclu_text = []
            for elt in rowsB:
                t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
                if elt[2] is not None:
                    t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
                exclu_text.append(t)

            exclu_text = "\n".join(exclu_text)
            emb.add_field(name=get_text("shop.exclusive_items", self.lang), value=exclu_text)

        emb.add_field(name=get_text("shop.global_items", self.lang), value=text, inline=False)

        await interaction.response.edit_message(embed=emb, view=ShopBrowserView(category='colors', lang=self.lang))


class ShopPerksButton(Button):  #"lang
    def __init__(self, disabled: bool, lang: str):
        super().__init__(
            label=get_text("view.shop.perks", ""),
            style=ButtonStyle.blurple,
            custom_id="shop:perks_section",
            disabled=disabled
        )
        self.lang = lang

    async def callback(self, interaction: Interaction):
        curA.execute(f"SELECT objectID, price, need "
                     f"FROM objects WHERE category='perks' AND locked=0 AND exclusive=0;")
        rowsA = curA.fetchall()

        curB.execute(f"SELECT objectID, price, need AS need_extID "
                     f"FROM objects WHERE category='perks' AND locked=0 AND exclusive=1;")
        rowsB = curB.fetchall()

        emb = Embed(color=Color.dark_blue(), description=get_text("shop.perks.desc", self.lang))\
            .set_author(name=get_text("shop.title.perks", self.lang))\
            .set_footer(text=get_text("shop.footer", self.lang))

        currency_logo = get_parameter('currency-logo')

        text = []
        for elt in rowsA:
            t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
            if elt[2] is not None:
                t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
            text.append(t)

        text = "\n".join(text)

        if len(rowsB) > 0:
            exclu_text = []
            for elt in rowsB:
                t = f"` ❱ ` {get_text(f'items.{elt[0]}.name', self.lang)} - {elt[1]} {currency_logo}"
                if elt[2] is not None:
                    t += f"\n<:blank:988098422663942146>Need : {get_text(f'items.{elt[2]}.name', self.lang)}"
                exclu_text.append(t)

            exclu_text = "\n".join(exclu_text)
            emb.add_field(name=get_text("shop.exclusive_items", self.lang), value=exclu_text, inline=False)

        emb.add_field(name=get_text("shop.global_items", self.lang), value=text, inline=False)

        await interaction.response.edit_message(embed=emb, view=ShopBrowserView(category='perks', lang=self.lang))


#######################################
#                                     #
#              ADMIN COG              #
#                                     #
#######################################

###############################
#         ADMIN CODES         #
###############################

class AdminCodesView(View):
    def __init__(self, pages: list = None):
        super().__init__(
            timeout=None
        )
        self.pages = []

        # discontinued -> will be replaced by commands
        # Add code
        # Edit code
        # Remove code

        # Previous page -> add page number in embed
        self.add_item(AdminCodesCloseButton())
        self.add_item(AdminCodesRefreshButton())
        self.add_item(AdminCodesToggleButton())
        self.add_item(AdminCodesDetailButton())
        # Next page


class AdminCodesModal(Modal):
    def __init__(self, title: str, cb) -> None:
        super().__init__(
            title=title
        )
        self.cb = cb

        self.add_item(InputText(label="Input codes separated by commas"))

    async def callback(self, interaction: Interaction):
        codes = self.children[0].value.split(',')
        await self.cb(interaction, codes)


class AdminCodesCloseButton(Button):
    def __init__(self):
        super().__init__(
            label="Close",  #get_text("view.button.close", ""),
            style=ButtonStyle.red,
            custom_id="admin:codes:close"
        )

    async def callback(self, interaction: Interaction):
        await self.view.message.delete()


class AdminCodesRefreshButton(Button):
    def __init__(self):
        super().__init__(
            label="Refresh",  #get_text("view.admin.codes.refresh", ""),
            style=ButtonStyle.grey,
            custom_id="admin:codes:refresh"
        )

    async def callback(self, interaction: Interaction):

        codes = get_codes_data()

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
        await self.view.message.edit(embed=codes_emb, view=self.view)
        await interaction.response.send_message("\u200b", ephemeral=True, delete_after=0.1)


class AdminCodesToggleButton(Button):
    def __init__(self):
        super().__init__(
            label="Toggle",  # get_text("view.admin.codes.toggle", ""),
            style=ButtonStyle.grey,
            custom_id="admin:codes:toggle"
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(AdminCodesModal("Codes toggle", toggle_callback))


async def toggle_callback(interaction: Interaction, codes_to_toggle):
    codes = get_codes_data()
    resume = []
    for code in codes_to_toggle:
        if code in codes:
            status = codes[code]['disabled']
            codes[code]['disabled'] = not status
            resume.append(f"{'+' if status else '-'} {code}")
        else:
            resume.append(f"? {code}")

    with open("json/codes.json", "w", encoding="utf-8") as code_file:
        json_dump(codes, code_file, indent=2)
    await interaction.response.send_message(f"```diff\n" + "\n".join(resume) + "\n```", ephemeral=True)


class AdminCodesDetailButton(Button):
    def __init__(self):
        super().__init__(
            label="Details",  # get_text("view.admin.codes.details", ""),
            style=ButtonStyle.blurple,
            custom_id="admin:codes:details"
        )

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(AdminCodesModal("Codes details", details_callback))


async def details_callback(interaction: Interaction, codes_to_detail):
    codes = get_codes_data()
    embeds = []
    failed = []

    if len(codes_to_detail) > 10:
        codes_to_detail = codes_to_detail[:10]
        limit_exceeded = True

    else:
        limit_exceeded = False

    for code in codes_to_detail:
        """
            "money": {
                "effect": "money",
                "extra": 50,
                "usage_limit": [
                  -1,
                  "all"
                ],
                "used_by": {
                  "444504367152889877": [
                    1690635568,
                    1690635588
                  ]
                },
                "usage_count": 2,
                "disabled": true
            }
        """
        if code in codes:
            code_data = codes[code]
            user_count = len(code_data['used_by'])
            emb_desc = f"**Identifier :** `{code}`\n" \
                       f"**Effect :** `{code_data['effect']}`\n" \
                       f"**Used :** `{code_data['usage_count']}` time{'s' if code_data['usage_count'] > 1 else ''} " \
                       f"by `{user_count}` user{'s' if user_count > 1 else ''}\n" \
                       f"**Usage limits :** `{code_data['usage_limit'][0]}` (`{code_data['usage_limit'][1]}`)\n" \
                       f"**Disabled : ** `{code_data['disabled']}`"
            emb = Embed(color=0x2b2d31, description=emb_desc).set_author(name=f"Code details - {code}")
            embeds.append(emb)

        else:
            failed.append(code)

    warning_message = ":warning: Only 10 codes can be detailed at once" if limit_exceeded else ""
    failed_message = f"\n:warning:  The following codes couldn't be found :\n> {', '.join(failed)}" if len(failed) > 0 else ""
    await interaction.response.send_message(warning_message + failed_message, embeds=embeds, ephemeral=True)
