import discord

def registrar_logs(bot, CANAL_LOG, SERVIDOR_TESTE=None, CANAIS_TESTE=None):
    @bot.event
    async def on_guild_join(guild):
        canal = bot.get_channel(CANAL_LOG)

        dono = getattr(guild, "owner", None)
        dono_info = f"{dono} (ID: {dono.id})" if dono else "Desconhecido"

        if canal:
            await canal.send(
                f"⚠️ O bot foi adicionado ao servidor **{guild.name}** (ID: {guild.id}) "
                f"pelo dono **{dono_info}**. Verifique licença!"
            )

    @bot.event
    async def on_guild_remove(guild):
        canal = bot.get_channel(CANAL_LOG)
        if canal:
            await canal.send(
                f"🚪 O bot foi removido do servidor **{guild.name}** (ID: {guild.id})."
            )
