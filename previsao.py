import discord
from discord import app_commands
from logica import find_mapping_and_pattern, format_rounds, P1, P2

# Guardar dados por servidor
sessao = {}

def registrar_previsao(bot, SERVIDOR_TESTE=None, CANAIS_TESTE=None, ativacao_dados=None):
    tree = bot.tree

# ---------------------- Comando principal ----------------------
    @tree.command(name="previsao", description="Inicia a previsão com os jogadores e confrontos")
    async def previsao(interaction: discord.Interaction):
        servidor_id = interaction.guild.id
        canal_id = interaction.channel.id

        # Verifica autorização
        autorizado = False
        if SERVIDOR_TESTE and CANAIS_TESTE and ativacao_dados:
            if servidor_id == SERVIDOR_TESTE or canal_id in CANAIS_TESTE:
                autorizado = True
            else:
                dados = ativacao_dados()
                for chave, info in dados["licencas"].items():
                    if info and info.get("servidor_id") == servidor_id:
                        from ativacao import licencia_valida
                        if licencia_valida(info):
                            autorizado = True
                            break
        if not autorizado:
            await interaction.response.send_message("❌ Este servidor não está autorizado.", ephemeral=True)
            return

        # Criar sessão vazia para esse servidor
        sessao[servidor_id] = {"players": [], "rounds": []}

        await interaction.response.send_message(
            "🔹 Vamos começar! \nDigite os 8 jogadores separados por vírgula, na ordem que você quiser. \n(*Ex: Vale, Karina, Layla, Lukas, Kagura, Nana, Miya, Dyrroth*)."
        )

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        # Espera mensagem do usuário com os jogadores
        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
            players = [p.strip() for p in msg.content.split(",")]
            if len(players) != 8 or len(set(players)) != 8:
                await interaction.channel.send("❌ Devem ser **8 nomes únicos**. Tente novamente com `/previsao`.")
                return
            sessao[servidor_id]["players"] = players

            await interaction.channel.send(
                "✅ Jogadores cadastrados! Agora, digite os confrontos das 4 primeiras rodadas.\n"
                "**Formato**: Cada rodada em uma linha, 4 partidas separadas por vírgula, com nomes separados por '**x**'.\n"
                "`Exemplo da 1ª rodada: Vale x Layla, Karina x Lukas, Kagura x Nana, Miya x Dyrroth`"
            )

            # Coletar 4 rodadas
            rounds = []
            for i in range(4):
                await interaction.channel.send(f"Digite a **Rodada {i+1}**:")
                msg_r = await bot.wait_for("message", check=check, timeout=180)
                partidas = msg_r.content.split(",")
                if len(partidas) != 4:
                    await interaction.channel.send("❌ Cada rodada deve ter 4 partidas. \nReinicie com `/previsao`.")
                    return
                rodada_set = set()
                for p in partidas:
                    try:
                        a,b = [x.strip() for x in p.split("x")]
                        rodada_set.add(frozenset([a,b]))
                    except:
                        await interaction.channel.send("❌ Formato incorreto. \nUse 'Jogador1 x Jogador2'. Reinicie com `/previsao`.")
                        return
                rounds.append(rodada_set)
            sessao[servidor_id]["rounds"] = rounds

            # ------------------- Calcular padrão -------------------
            mapping, pattern_name = find_mapping_and_pattern(rounds, players)
            if not mapping:
                await interaction.channel.send("❌ Não foi possível identificar padrão com essas rodadas.")
                return
            pattern = P1 if pattern_name == "P1" else P2
            rounds_text = format_rounds(mapping, pattern)
            enum_text = "\n".join([f"{i}: {mapping[i]}" for i in range(1,9)])

            # Salvar na sessão para /sequencia
            sessao[servidor_id]["mapping"] = mapping
            sessao[servidor_id]["pattern"] = pattern

            # Enviar resultado final
            await interaction.channel.send(
                f"✅ **Padrão encontrado: {pattern_name}**\n\n"
                f"**Rodadas 5-14:**\n{rounds_text}\n\n"
                f"**Enumeração dos jogadores:**\n{enum_text}"
            )

        except Exception as e:
            await interaction.channel.send(f"❌ Tempo esgotado ou erro: {e}")

    # ---------------------- Sequência do jogador ----------------------
    @tree.command(name="sequencia", description="Mostra a sequência de um jogador")
    @app_commands.describe(numero="Número do jogador (1-8)")
    async def sequencia(interaction: discord.Interaction, numero: int):
        guild_id = interaction.guild.id
        if guild_id not in sessao or "mapping" not in sessao[guild_id]:
            await interaction.response.send_message("⚠️ Primeiro gere uma previsão com `/previsao`.")
            return

        mapping = sessao[guild_id]["mapping"]
        pattern = sessao[guild_id]["pattern"]

        if numero not in mapping:
            await interaction.response.send_message(f"Jogador {numero} não encontrado.")
            return

        name = mapping[numero]
        seq = [f"\nSequência do Jogador {numero} → {name}"]
        for r in range(1, 15):
            for a,b in pattern[r]:
                if a==numero or b==numero:
                    opp = mapping[b] if a==numero else mapping[a]
                    seq.append(f"  Rodada {r}: {name} x {opp}")
                    break
        await interaction.response.send_message(f"```{chr(10).join(seq)}```")
