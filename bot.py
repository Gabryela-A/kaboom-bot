import os
import discord
from discord.ext import commands
from ativacao import registrar_comandos, carregar_dados
from previsao import registrar_previsao
from logs import registrar_logs
from keep_alive import keep_alive  # 🔹 importa o keep_alive

# ------------------ Variáveis ------------------
TOKEN = os.environ.get("DISCORD_TOKEN")  # pega token da variável de ambiente
if TOKEN is None:
    raise ValueError("❌ ERRO: Token do bot não encontrado! Defina a variável de ambiente DISCORD_TOKEN.")

DONO_ID = 773047587812409354
CANAL_LOG = 1415890541605945446
SERVIDOR_TESTE = 1032008790079459508
CANAIS_TESTE = [111111111111111111, 222222222222222222]

# ------------------ Configuração do bot ------------------
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Registrar comandos
registrar_comandos(bot, DONO_ID, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE)
registrar_previsao(bot, SERVIDOR_TESTE, CANAIS_TESTE, ativacao_dados=carregar_dados)
registrar_logs(bot, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE)

# ------------------ Check global de licença ------------------
@bot.check
async def verificar_licenca(ctx: commands.Context):
    from ativacao import carregar_dados, licencia_valida, servidor_sem_expiracao, canal_sem_expiracao

    # Testes sempre liberados
    if servidor_sem_expiracao(ctx.guild.id, SERVIDOR_TESTE) or canal_sem_expiracao(ctx.channel.id, CANAIS_TESTE):
        return True

    # Comando /ativar sempre liberado
    if ctx.command and ctx.command.name == "ativar":
        return True

    # Verificar licença no servidor
    dados = carregar_dados()
    for chave, info in dados["licencas"].items():
        if info and info.get("servidor_id") == ctx.guild.id:
            if licencia_valida(info):
                return True

    # Se não houver licença válida → bloqueia e avisa apenas o usuário
    try:
        await ctx.send(
            "❌ Este bot ainda não foi ativado neste servidor.\nEntre em contato com o dono para obter uma chave.",
            delete_after=15
        )
    except:
        pass
    return False

# ------------------ Evento on_ready ------------------
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    await bot.tree.sync()

# ------------------ Rodar bot ------------------
if __name__ == "__main__":
    keep_alive()  # 🔹 mantém vivo no Render
    bot.run(TOKEN)
