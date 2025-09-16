import os
import secrets
import asyncio
from datetime import datetime, timezone
import discord
from discord.ext import tasks
from typing import Dict, Any

import db  # nosso módulo de DB

DATA_FIM_TEMPORADA = "2025-11-18T23:59:59"  # string ISO do exemplo
_CACHE: Dict[str, Any] = {"licencas": {}, "servidores": []}
_cache_lock = asyncio.Lock()

# ---------------- Funções utilitárias ----------------
def gerar_chave():
    return secrets.token_hex(4).upper()

def _parse_iso_with_utc(s: str):
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def licencia_valida(info_licenca):
    if not info_licenca or "data_expiracao" not in info_licenca or info_licenca["data_expiracao"] is None:
        return False
    data_expiracao = _parse_iso_with_utc(info_licenca["data_expiracao"])
    return datetime.now(timezone.utc) <= data_expiracao

def servidor_sem_expiracao(guild_id, servidor_teste):
    return guild_id == servidor_teste

def canal_sem_expiracao(channel_id, canais_teste):
    return channel_id in canais_teste

# ---------------- Cache helpers ----------------
async def _refresh_cache():
    """Atualiza cache a partir do DB"""
    async with _cache_lock:
        licencas = await db.fetch_all_licencas()
        servidores = await db.fetch_servidores()
        _CACHE["licencas"] = {k: v for k, v in licencas.items()}
        _CACHE["servidores"] = servidores

def carregar_dados():
    """Snapshot em memória"""
    return {"licencas": dict(_CACHE["licencas"]), "servidores": list(_CACHE["servidores"])}

# ---------------- Registrar comandos ----------------
def registrar_comandos(bot, DONO_ID, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE):
    tree = bot.tree

    @tree.command(name="ativar", description="Ativa o bot no servidor usando uma chave")
    async def ativar(interaction: discord.Interaction, chave: str):
        if servidor_sem_expiracao(interaction.guild.id, SERVIDOR_TESTE) or canal_sem_expiracao(interaction.channel.id, CANAIS_TESTE):
            await db.add_servidor(interaction.guild.id)
            await _refresh_cache()
            await interaction.response.send_message("✅ Servidor/canal de teste ativado sem prazo de validade!", ephemeral=True)
            return

        row = await db.get_licenca_row(chave)
        if not row:
            await interaction.response.send_message("❌ Chave inválida.", ephemeral=True)
            canal = bot.get_channel(CANAL_LOG)
            if canal:
                await canal.send(
                    f"🚨 Tentativa de ativação inválida no servidor {interaction.guild.name} (ID: {interaction.guild.id}) "
                    f"por {interaction.user} (ID: {interaction.user.id})"
                )
            return

        info_licenca = {
            "servidor_id": row["servidor_id"],
            "data_expiracao": row["data_expiracao"].isoformat() if row["data_expiracao"] else None
        }

        if info_licenca.get("servidor_id") and not licencia_valida(info_licenca):
            await db.clear_licenca(chave)

        data_exp = _parse_iso_with_utc(DATA_FIM_TEMPORADA)
        await db.assign_licenca(chave, interaction.guild.id, data_exp)
        await db.add_servidor(interaction.guild.id)
        await _refresh_cache()
        await interaction.response.send_message(f"✅ Bot ativado! Licença válida até {DATA_FIM_TEMPORADA}.", ephemeral=True)

    @tree.command(name="gerar_licenca", description="(Dono) Gera uma nova chave de licença")
    async def gerar_licenca(interaction: discord.Interaction):
        if interaction.user.id != DONO_ID:
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        nova_chave = gerar_chave()
        await db.insert_licenca(nova_chave)
        await _refresh_cache()
        await interaction.response.send_message(f"✅ Nova chave: **{nova_chave}**", ephemeral=True)

    # ---------------- Limpeza automática ----------------
    @tasks.loop(hours=24)
    async def limpar_licencas_expiradas():
        now = datetime.now(timezone.utc)
        removed = await db.clear_expired_and_get_removed_servers(now)
        if removed:
            canal = bot.get_channel(CANAL_LOG)
            if canal:
                for s in removed:
                    await canal.send(f"⚠️ Licença expirada e servidor removido: **{s}**")
            await _refresh_cache()

    return limpar_licencas_expiradas
