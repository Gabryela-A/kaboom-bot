import itertools

# -------------------- Padrões --------------------
P1 = {
    1: [(1,2), (3,4), (5,6), (7,8)],
    2: [(1,6), (2,5), (3,8), (4,7)],
    3: [(1,5), (2,6), (3,7), (4,8)],
    4: [(1,3), (2,4), (5,7), (6,8)],
    5: [(1,4), (2,3), (5,8), (6,7)],
    6: [(1,8), (2,7), (3,6), (4,5)],
    7: [(1,7), (2,8), (3,5), (4,6)],
}
for r in range(8, 15):
    P1[r] = P1[(r-1) % 7 + 1]

P2 = {
    1: [(1,7), (2,8), (3,6), (4,5)],
    2: [(1,8), (2,3), (5,6), (4,7)],
    3: [(1,3), (2,5), (4,6), (7,8)],
    4: [(1,5), (2,4), (3,8), (6,7)],
    5: [(1,4), (2,6), (3,7), (5,8)],
    6: [(1,6), (2,7), (3,5), (4,8)],
    7: [(1,2), (3,4), (5,7), (6,8)],
    8: [(1,7), (2,6), (3,8), (4,5)],
    9: [(1,5), (2,8), (3,6), (4,7)],
    10: [(1,4), (2,3), (5,6), (7,8)],
    11: [(1,8), (2,4), (3,5), (6,7)],
    12: [(1,3), (2,5), (4,6), (7,8)],
    13: [(1,2), (3,7), (4,8), (5,6)],
    14: [(1,6), (2,7), (3,4), (5,8)],
}

# -------------------- Funções --------------------
def find_mapping_and_pattern(user_rounds, players):
    nums = list(range(1,9))
    patterns = [("P1", P1), ("P2", P2)]
    players_list = list(players)
    for pname, pat in patterns:
        for perm in itertools.permutations(players_list):
            mapping = dict(zip(nums, perm))
            ok = True
            for r in range(4):
                expected = set(frozenset([mapping[a], mapping[b]]) for (a,b) in pat[r+1])
                if expected != user_rounds[r]:
                    ok = False
                    break
            if ok:
                return mapping, pname
    return None, None

def format_rounds(mapping, pattern):
    out = []
    for r in range(5,15):
        pairs = [(mapping[a], mapping[b]) for (a,b) in pattern[r]]
        parts_str = ", ".join(f"{a} x {b}" for a,b in pairs)
        out.append(f"Rodada {r}: {parts_str}")
    return "\n".join(out)
