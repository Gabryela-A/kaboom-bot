import os
import discord
from discord.ext import commands
from ativacao import registrar_comandos, carregar_dados
from previsao import registrar_previsao
from logs import registrar_logs
from keep_alive import keep_alive
import db  # DB

# ---------------- Variáveis ----------------
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ ERRO: Token do bot não encontrado!")

DONO_ID = 773047587812409354
CANAL_LOG = 1417957707901829151
SERVIDOR_TESTE = 1032008790079459508
CANAIS_TESTE = [1417649122973978827, 222222222222222222]

# ---------------- Configuração do bot ----------------
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------------- Registrar comandos ----------------
limpar_licencas = registrar_comandos(bot, DONO_ID, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE)
registrar_previsao(bot, SERVIDOR_TESTE, CANAIS_TESTE, ativacao_dados=carregar_dados)
registrar_logs(bot, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE)

# ---------------- Check global de licença ----------------
@bot.check
async def verificar_licenca(ctx: commands.Context):
    from ativacao import licencia_valida, servidor_sem_expiracao, canal_sem_expiracao

    if servidor_sem_expiracao(ctx.guild.id, SERVIDOR_TESTE) or canal_sem_expiracao(ctx.channel.id, CANAIS_TESTE):
        return True
    if ctx.command and ctx.command.name == "ativar":
        return True

    dados = carregar_dados()
    for info in dados["licencas"].values():
        if info.get("servidor_id") == ctx.guild.id and licencia_valida(info):
            return True

    try:
        await ctx.send("❌ Este bot ainda não foi ativado neste servidor.", delete_after=15)
    except:
        pass
    return False

# ---------------- Evento on_ready ----------------
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    await bot.tree.sync()

    # Inicializa DB e cache
    try:
        await db.init_pool(os.environ.get("DATABASE_URL"))
        await carregar_dados()
        print("✅ DB inicializado com sucesso!")
    except Exception as e:
        print("❌ Erro inicializando DB:", e)

    # Inicia limpeza de licenças expiradas
    try:
        limpar_licencas.start()
    except Exception as e:
        print("⚠️ Erro iniciando limpeza de licenças:", e)

# ---------------- Rodar bot ----------------
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
