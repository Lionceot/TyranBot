from discord.ui import View, Button
from discord import ButtonStyle, User, Interaction

from main import db, get_parameter, get_text

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
