import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

from logica import find_mapping_and_pattern, format_rounds, P1, P2

# Guardar dados por servidor
sessao = {}

# ---------------------- Select Menu personalizado ----------------------
class PartidaSelect(Select):
    def __init__(self, jogadores, rodada, partidas, callback_fim):
        options = [discord.SelectOption(label=j, value=j) for j in jogadores]
        super().__init__(placeholder=f"Rodada {rodada}: escolha um jogador", options=options, min_values=1, max_values=1)
        self.jogadores = jogadores
        self.rodada = rodada
        self.partidas = partidas
        self.callback_fim = callback_fim
        self.escolhidos = []

    async def callback(self, interaction: discord.Interaction):
        escolhido = self.values[0]
        self.escolhidos.append(escolhido)

        if len(self.escolhidos) == 2:
            # Monta partida
            a, b = self.escolhidos
            self.partidas.append(frozenset([a, b]))
            await interaction.response.send_message(f"✅ Partida registrada: **{a} x {b}**", ephemeral=True)

            # Remove escolhidos da lista
            self.jogadores.remove(a)
            self.jogadores.remove(b)

            # Se já tem 4 partidas, fecha a rodada
            if len(self.partidas) == 4:
                await self.callback_fim(interaction, self.partidas)
            else:
                # Limpa seleção para próxima partida
                self.escolhidos = []
                self.options = [discord.SelectOption(label=j, value=j) for j in self.jogadores]
                await interaction.followup.send("👉 Escolha o próximo jogador", view=self.view)


class RodadaView(View):
    def __init__(self, jogadores, rodada, callback_fim):
        super().__init__(timeout=180)
        self.partidas = []
        self.add_item(PartidaSelect(jogadores, rodada, self.partidas, callback_fim))


# ---------------------- Menu para escolher jogador ----------------------
class JogadorSelect(Select):
    def __init__(self, mapping, pattern):
        options = [discord.SelectOption(label=f"{i}: {nome}", value=str(i)) for i, nome in mapping.items()]
        super().__init__(placeholder="Escolha um jogador", options=options, min_values=1, max_values=1)
        self.mapping = mapping
        self.pattern = pattern

    async def callback(self, interaction: discord.Interaction):
        numero = int(self.values[0])
        name = self.mapping[numero]
        seq = [f"\nSequência do Jogador {numero} → {name}"]

        for r in range(1, 15):
            for a, b in self.pattern[r]:
                if a == numero or b == numero:
                    opp = self.mapping[b] if a == numero else self.mapping[a]
                    seq.append(f"  Rodada {r}: {name} x {opp}")
                    break

        await interaction.response.send_message(f"```{chr(10).join(seq)}```")


class JogadorView(View):
    def __init__(self, mapping, pattern):
        super().__init__(timeout=120)
        self.add_item(JogadorSelect(mapping, pattern))


# ---------------------- Função principal ----------------------
def registrar_previsao(bot, SERVIDOR_TESTE=None, CANAIS_TESTE=None, ativacao_dados=None):
    tree = bot.tree

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
            "🔹 Vamos começar! \nDigite os 8 jogadores separados por vírgula, na ordem que você quiser.\n"
            "(*Exemplo*: Vale, Karina, Layla, Lukas, Kagura, Nana, Miya, Dyrroth)"
        )

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            # Captura jogadores
            msg = await bot.wait_for("message", check=check, timeout=120)
            players = [p.strip() for p in msg.content.split(",")]
            if len(players) != 8 or len(set(players)) != 8:
                await interaction.channel.send("❌ Devem ser **8 nomes únicos**. Reinicie com `/previsao`.")
                return
            sessao[servidor_id]["players"] = players

            await interaction.channel.send("✅ Jogadores cadastrados! Agora vamos montar as **4 primeiras rodadas** usando o menu suspenso.")

            rounds = []

            # Função chamada no fim de cada rodada
            async def fim_da_rodada(inter, partidas):
                rounds.append(set(partidas))

                if len(rounds) < 4:
                    # Próxima rodada
                    view = RodadaView(players.copy(), len(rounds)+1, fim_da_rodada)
                    await inter.channel.send(f"👉 Escolha os confrontos da **Rodada {len(rounds)+1}**:", view=view)
                else:
                    # 4 rodadas concluídas → calcular padrão
                    sessao[servidor_id]["rounds"] = rounds
                    mapping, pattern_name = find_mapping_and_pattern(rounds, players)
                    if not mapping:
                        await inter.channel.send("❌ Não foi possível identificar padrão com essas rodadas.")
                        return
                    pattern = P1 if pattern_name == "P1" else P2
                    rounds_text = format_rounds(mapping, pattern)
                    enum_text = "\n".join([f"{i}: {mapping[i]}" for i in range(1, 9)])

                    sessao[servidor_id]["mapping"] = mapping
                    sessao[servidor_id]["pattern"] = pattern

                    await inter.channel.send(
                        f"✅ **Padrão encontrado: {pattern_name}**\n\n"
                        f"**Rodadas 5-14:**\n{rounds_text}\n\n"
                        f"**Enumeração dos jogadores:**\n{enum_text}"
                    )

        except Exception as e:
            await interaction.channel.send(f"❌ Tempo esgotado ou erro: {e}")


    # ---------------------- Sequência do jogador ----------------------
    @tree.command(name="sequencia", description="Mostra a sequência de um jogador")
    async def sequencia(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in sessao or "mapping" not in sessao[guild_id]:
            await interaction.response.send_message("⚠️ Primeiro gere uma previsão com `/previsao`.")
            return

        mapping = sessao[guild_id]["mapping"]
        pattern = sessao[guild_id]["pattern"]

        view = JogadorView(mapping, pattern)
        await interaction.response.send_message("👉 Escolha um jogador para ver a sequência:", view=view)
