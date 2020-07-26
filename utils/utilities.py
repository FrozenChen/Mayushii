import asyncio


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
