import json
import os
import secrets
from datetime import datetime, timezone
import discord
from discord.ext import tasks

ARQUIVO_DADOS = "licencas.json"
DATA_FIM_TEMPORADA = "2025-11-18T23:59:59"

def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "w") as f:
            json.dump({"licencas": {}, "servidores": []}, f)
    with open(ARQUIVO_DADOS, "r") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w") as f:
        json.dump(dados, f, indent=4)

def licencia_valida(info_licenca):
    if not info_licenca or "data_expiracao" not in info_licenca:
        return False
    data_expiracao = datetime.fromisoformat(info_licenca["data_expiracao"])
    if data_expiracao.tzinfo is None:
        data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= data_expiracao

def gerar_chave():
    return secrets.token_hex(4).upper()

def servidor_sem_expiracao(guild_id, servidor_teste):
    return guild_id == servidor_teste

def canal_sem_expiracao(channel_id, canais_teste):
    return channel_id in canais_teste


def registrar_comandos(bot, DONO_ID, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE):
    tree = bot.tree

    @tree.command(name="ativar", description="Ativa o bot no servidor usando uma chave")
    async def ativar(interaction: discord.Interaction, chave: str):
        dados = carregar_dados()

        # Servidor/canal de teste sempre liberado
        if servidor_sem_expiracao(interaction.guild.id, SERVIDOR_TESTE) or canal_sem_expiracao(interaction.channel.id, CANAIS_TESTE):
            if interaction.guild.id not in dados["servidores"]:
                dados["servidores"].append(interaction.guild.id)
                salvar_dados(dados)
            await interaction.response.send_message("✅ Servidor/canal de teste ativado sem prazo de validade!", ephemeral=True)
            return

        # Verificação da chave
        if chave not in dados["licencas"]:
            await interaction.response.send_message("❌ Chave inválida. Entre em contato com o dono.", ephemeral=True)
            canal = bot.get_channel(CANAL_LOG)
            if canal:
                await canal.send(
                    f"🚨 Tentativa de ativação inválida no servidor {interaction.guild.name} (ID: {interaction.guild.id}) "
                    f"por {interaction.user} (ID: {interaction.user.id})"
                )
            return

        info_licenca = dados["licencas"][chave]
        if info_licenca and "servidor_id" in info_licenca:
            servidor_id = info_licenca["servidor_id"]
            if licencia_valida(info_licenca):
                await interaction.response.send_message("❌ Essa chave já está ativa em outro servidor.", ephemeral=True)
                return
            else:
                # Remove licença expirada de outro servidor
                if servidor_id in dados["servidores"]:
                    dados["servidores"].remove(servidor_id)
                dados["licencas"][chave] = None

        # Ativa com prazo fixo
        dados["licencas"][chave] = {
            "servidor_id": interaction.guild.id,
            "data_expiracao": DATA_FIM_TEMPORADA
        }
        if interaction.guild.id not in dados["servidores"]:
            dados["servidores"].append(interaction.guild.id)
        salvar_dados(dados)

        await interaction.response.send_message(
            f"✅ Bot ativado! Licença válida até {DATA_FIM_TEMPORADA}.", ephemeral=True
        )

    @tree.command(name="gerar_licenca", description="(Dono) Gera uma nova chave de licença")
    async def gerar_licenca(interaction: discord.Interaction):
        if interaction.user.id != DONO_ID:
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        nova_chave = gerar_chave()
        dados = carregar_dados()
        dados["licencas"][nova_chave] = None
        salvar_dados(dados)
        await interaction.response.send_message(f"✅ Nova chave: **{nova_chave}**", ephemeral=True)

    # ---------------- LIMPEZA AUTOMÁTICA ----------------
    @tasks.loop(hours=24)
    async def limpar_licencas_expiradas():
        dados = carregar_dados()
        alterado = False
        for chave, info in list(dados["licencas"].items()):
            if info and "servidor_id" in info:
                servidor_id = info["servidor_id"]
                if not servidor_sem_expiracao(servidor_id, SERVIDOR_TESTE) and not licencia_valida(info):
                    if servidor_id in dados["servidores"]:
                        dados["servidores"].remove(servidor_id)
                    dados["licencas"][chave] = None
                    alterado = True
                    canal = bot.get_channel(CANAL_LOG)
                    if canal:
                        await canal.send(f"⚠️ Licença expirada e servidor removido: **{servidor_id}**")
        if alterado:
            salvar_dados(dados)

    @bot.event
    async def on_ready():
        limpar_licencas_expiradas.start()
