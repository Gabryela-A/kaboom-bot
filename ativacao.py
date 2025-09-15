import os
import secrets
import asyncio
from datetime import datetime, timezone
import discord
from discord.ext import tasks
from typing import Dict, Any

import db  # nosso novo módulo

ARQUIVO_DADOS = "licencas.json"  # só para referência; não usamos mais para persistência
DATA_FIM_TEMPORADA = "2025-11-18T23:59:59"  # string ISO (sem TZ) do seu exemplo

# cache em memória (para compatibilidade com funções que chamam carregar_dados())
_CACHE: Dict[str, Any] = {"licencas": {}, "servidores": []}
_cache_lock = asyncio.Lock()

def gerar_chave():
    return secrets.token_hex(4).upper()

def _parse_iso_with_utc(s: str):
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
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

# ---------- cache helpers ----------
async def _refresh_cache():
    """Lê do DB e atualiza _CACHE (chamado periodicamente e após mudanças)."""
    async with _cache_lock:
        licencas = await db.fetch_all_licencas()
        servidores = await db.fetch_servidores()
        _CACHE["licencas"] = {k: v for k, v in licencas.items()}  # v já tem data_expiracao em iso ou None
        _CACHE["servidores"] = servidores

def carregar_dados():
    """Retorna snapshot em memória no formato antigo: {'licencas': {...}, 'servidores': [...] }"""
    # retornamos cópia rasa (suficiente)
    return {"licencas": dict(_CACHE["licencas"]), "servidores": list(_CACHE["servidores"])}

# ---------- registrar comandos ----------
def registrar_comandos(bot, DONO_ID, CANAL_LOG, SERVIDOR_TESTE, CANAIS_TESTE):
    tree = bot.tree

    @tree.command(name="ativar", description="Ativa o bot no servidor usando uma chave")
    async def ativar(interaction: discord.Interaction, chave: str):
        # Servidor/canal de teste sempre liberado
        if servidor_sem_expiracao(interaction.guild.id, SERVIDOR_TESTE) or canal_sem_expiracao(interaction.channel.id, CANAIS_TESTE):
            # registra servidor na tabela de servidores (persistente)
            await db.add_servidor(interaction.guild.id)
            await _refresh_cache()
            await interaction.response.send_message("✅ Servidor/canal de teste ativado sem prazo de validade!", ephemeral=True)
            return

        # Verificação da chave
        row = await db.get_licenca_row(chave)
        if not row:
            await interaction.response.send_message("❌ Chave inválida. Entre em contato com o dono.", ephemeral=True)
            canal = bot.get_channel(CANAL_LOG)
            if canal:
                await canal.send(
                    f"🚨 Tentativa de ativação inválida no servidor {interaction.guild.name} (ID: {interaction.guild.id}) "
                    f"por {interaction.user} (ID: {interaction.user.id})"
                )
            return

        # row tem servidor_id e data_expiracao (datetime or None)
        info_licenca = {
            "servidor_id": row["servidor_id"],
            "data_expiracao": row["data_expiracao"].isoformat() if row["data_expiracao"] else None
        }

        if info_licenca and info_licenca.get("servidor_id"):
            servidor_id = info_licenca["servidor_id"]
            if licencia_valida(info_licenca):
                await interaction.response.send_message("❌ Essa chave já está ativa em outro servidor.", ephemeral=True)
                return
            else:
                # Remove licença expirada de outro servidor
                await db.clear_licenca(chave)
                # tenta remover servidor da tabela
                try:
                    await db._pool  # no-op: só pra evitar lint; não usado aqui
                except Exception:
                    pass

        # calcula data de expiração
        data_exp = _parse_iso_with_utc(DATA_FIM_TEMPORADA)
        # se a data_exp for sem tz, _parse adiciona UTC
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

    # ---------------- LIMPEZA AUTOMÁTICA ----------------
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

    @bot.event
    async def on_ready():
        # inicializa DB e cache assim que o bot estiver pronto
        try:
            await db.init_pool(os.environ.get("DATABASE_URL"))
            await _refresh_cache()
            limpar_licencas_expiradas.start()
        except Exception as e:
            print("Erro inicializando DB:", e)
