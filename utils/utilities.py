import disnake
import random


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

    @disnake.ui.button(label='Yes', style=disnake.ButtonStyle.green)
    async def confirm_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        self.value = True
        self.stop()

    @disnake.ui.button(label='No', style=disnake.ButtonStyle.red)
    async def deny_button(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        self.value = False
        self.stop()