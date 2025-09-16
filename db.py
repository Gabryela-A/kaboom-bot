# db.py
import os
import asyncio
import asyncpg
from typing import Optional, List, Dict, Any

_pool: Optional[asyncpg.pool.Pool] = None

async def init_pool(database_url: Optional[str] = None):
    """
    Inicializa o pool (chame no on_ready antes de usar o DB).
    Usa DATABASE_URL da env se database_url for None.
    """
    global _pool
    if _pool:
        return
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não encontrada (defina como variável de ambiente).")
    _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)

    # criar tabelas básicas se não existirem
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS licencas (
                chave TEXT PRIMARY KEY,
                servidor_id BIGINT,
                data_expiracao TIMESTAMPTZ
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS servidores (
                server_id BIGINT PRIMARY KEY
            );
        """)

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

# -------- operações utilitárias --------
async def fetch_all_licencas() -> Dict[str, Dict[str, Any]]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT chave, servidor_id, data_expiracao FROM licencas")
        out = {}
        for r in rows:
            out[r["chave"]] = {
                "servidor_id": r["servidor_id"],
                "data_expiracao": r["data_expiracao"].isoformat() if r["data_expiracao"] else None
            }
        return out

async def fetch_servidores() -> List[int]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT server_id FROM servidores")
        return [r["server_id"] for r in rows]

async def insert_licenca(chave: str):
    async with _pool.acquire() as conn:
        await conn.execute("INSERT INTO licencas(chave) VALUES($1) ON CONFLICT DO NOTHING", chave)

async def get_licenca_row(chave: str):
    async with _pool.acquire() as conn:
        return await conn.fetchrow("SELECT chave, servidor_id, data_expiracao FROM licencas WHERE chave = $1", chave)

async def assign_licenca(chave: str, servidor_id: int, data_expiracao):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE licencas SET servidor_id=$1, data_expiracao=$2 WHERE chave=$3",
            servidor_id, data_expiracao, chave
        )

async def clear_licenca(chave: str):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE licencas SET servidor_id=NULL, data_expiracao=NULL WHERE chave=$1", chave)

async def clear_expired_and_get_removed_servers(now):
    """
    Remove (set NULL) licenças expiradas e retorna lista de servidor_ids removidos.
    """
    removed_servers = []
    async with _pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                "SELECT chave, servidor_id FROM licencas WHERE servidor_id IS NOT NULL AND data_expiracao IS NOT NULL AND data_expiracao < $1",
                now
            )
            chaves = [r["chave"] for r in rows]
            removed_servers = [r["servidor_id"] for r in rows if r["servidor_id"] is not None]
            # atualiza cada licença (poucas licenças → ok)
            for c in chaves:
                await conn.execute("UPDATE licencas SET servidor_id=NULL, data_expiracao=NULL WHERE chave=$1", c)
            # remove servidores da tabela de servidores (se desejar)
            for s in removed_servers:
                await conn.execute("DELETE FROM servidores WHERE server_id=$1", s)
    return removed_servers

async def add_servidor(server_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("INSERT INTO servidores(server_id) VALUES($1) ON CONFLICT DO NOTHING", server_id)