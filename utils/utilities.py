import disnake
import random
import traceback

# thanks ihaveahax
def gen_color(seed) -> disnake.Color:
    random.seed(seed)
    c_r = random.randint(0, 255)
    c_g = random.randint(0, 255)
    c_b = random.randint(0, 255)
    return disnake.Color((c_r << 16) + (c_g << 8) + c_b)


class ConfirmationButtons(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @disnake.ui.button(label="Yes", style=disnake.ButtonStyle.green)
    async def confirm_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.value = True
        self.stop()

    @disnake.ui.button(label="No", style=disnake.ButtonStyle.red)
    async def deny_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.value = False
        self.stop()


def create_error_embed(inter, exc) -> disnake.Embed:
    embed = disnake.Embed(
        title=f"Unexpected exception in command {inter.application_command.name}",
        color=0xE50730,
    )
    trace = "".join(
        traceback.format_exception(etype=None, value=exc, tb=exc.__traceback__)
    )
    embed.description = f"```py\n{trace}```"
    embed.add_field(name="Exception Type", value=exc.__class__.__name__)
    embed.add_field(
        name="Information",
        value=f"channel: {inter.channel.mention if isinstance(inter.channel, disnake.TextChannel) else 'Direct Message'}\ncommand: {inter.application_command.name}\nauthor: {inter.author.mention}",
        inline=False,
    )
    return embed
