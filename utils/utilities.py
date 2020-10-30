import asyncio
import discord
import random


async def wait_for_answer(ctx):
    try:
        msg = await ctx.bot.wait_for(
            "message",
            timeout=15,
            check=lambda message: message.author == ctx.author
            and ("yes" in message.content or "no" in message.content),
        )
    except asyncio.TimeoutError:
        await ctx.send("You took too long 🐢")
        return None
    return "yes" in msg.content


# thanks ihaveahax
def gen_color(seed) -> discord.Color:
    random.seed(seed)
    c_r = random.randint(0, 255)
    c_g = random.randint(0, 255)
    c_b = random.randint(0, 255)
    return discord.Color((c_r << 16) + (c_g << 8) + c_b)
