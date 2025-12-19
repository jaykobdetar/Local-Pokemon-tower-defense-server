#!/usr/bin/env python3
"""
PTD Save Editor / Importer

Creates or edits save files for the PTD local server.
Can import Pokemon, set badges, money, etc.
"""

import json
import os
import random
import string
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "ptd_saves")

# Pokemon data
POKEMON_NAMES = {
    1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur",
    4: "Charmander", 5: "Charmeleon", 6: "Charizard",
    7: "Squirtle", 8: "Wartortle", 9: "Blastoise",
    10: "Caterpie", 11: "Metapod", 12: "Butterfree",
    13: "Weedle", 14: "Kakuna", 15: "Beedrill",
    16: "Pidgey", 17: "Pidgeotto", 18: "Pidgeot",
    19: "Rattata", 20: "Raticate",
    21: "Spearow", 22: "Fearow",
    23: "Ekans", 24: "Arbok",
    25: "Pikachu", 26: "Raichu",
    27: "Sandshrew", 28: "Sandslash",
    29: "Nidoran♀", 30: "Nidorina", 31: "Nidoqueen",
    32: "Nidoran♂", 33: "Nidorino", 34: "Nidoking",
    35: "Clefairy", 36: "Clefable",
    37: "Vulpix", 38: "Ninetales",
    39: "Jigglypuff", 40: "Wigglytuff",
    41: "Zubat", 42: "Golbat",
    43: "Oddish", 44: "Gloom", 45: "Vileplume",
    46: "Paras", 47: "Parasect",
    48: "Venonat", 49: "Venomoth",
    50: "Diglett", 51: "Dugtrio",
    52: "Meowth", 53: "Persian",
    54: "Psyduck", 55: "Golduck",
    56: "Mankey", 57: "Primeape",
    58: "Growlithe", 59: "Arcanine",
    60: "Poliwag", 61: "Poliwhirl", 62: "Poliwrath",
    63: "Abra", 64: "Kadabra", 65: "Alakazam",
    66: "Machop", 67: "Machoke", 68: "Machamp",
    69: "Bellsprout", 70: "Weepinbell", 71: "Victreebel",
    72: "Tentacool", 73: "Tentacruel",
    74: "Geodude", 75: "Graveler", 76: "Golem",
    77: "Ponyta", 78: "Rapidash",
    79: "Slowpoke", 80: "Slowbro",
    81: "Magnemite", 82: "Magneton",
    83: "Farfetch'd",
    84: "Doduo", 85: "Dodrio",
    86: "Seel", 87: "Dewgong",
    88: "Grimer", 89: "Muk",
    90: "Shellder", 91: "Cloyster",
    92: "Gastly", 93: "Haunter", 94: "Gengar",
    95: "Onix",
    96: "Drowzee", 97: "Hypno",
    98: "Krabby", 99: "Kingler",
    100: "Voltorb", 101: "Electrode",
    102: "Exeggcute", 103: "Exeggutor",
    104: "Cubone", 105: "Marowak",
    106: "Hitmonlee", 107: "Hitmonchan",
    108: "Lickitung",
    109: "Koffing", 110: "Weezing",
    111: "Rhyhorn", 112: "Rhydon",
    113: "Chansey",
    114: "Tangela",
    115: "Kangaskhan",
    116: "Horsea", 117: "Seadra",
    118: "Goldeen", 119: "Seaking",
    120: "Staryu", 121: "Starmie",
    122: "Mr. Mime",
    123: "Scyther",
    124: "Jynx",
    125: "Electabuzz",
    126: "Magmar",
    127: "Pinsir",
    128: "Tauros",
    129: "Magikarp", 130: "Gyarados",
    131: "Lapras",
    132: "Ditto",
    133: "Eevee", 134: "Vaporeon", 135: "Jolteon", 136: "Flareon",
    137: "Porygon",
    138: "Omanyte", 139: "Omastar",
    140: "Kabuto", 141: "Kabutops",
    142: "Aerodactyl",
    143: "Snorlax",
    144: "Articuno", 145: "Zapdos", 146: "Moltres",
    147: "Dratini", 148: "Dragonair", 149: "Dragonite",
    150: "Mewtwo", 151: "Mew",
    1010: "MissingNo"
}

def generate_save_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=14))

def load_account(email):
    """Load account data"""
    account_file = os.path.join(SAVE_DIR, f"{email}_account.json")
    if os.path.exists(account_file):
        with open(account_file, 'r') as f:
            return json.load(f)
    return None

def save_account(email, account):
    """Save account data"""
    os.makedirs(SAVE_DIR, exist_ok=True)
    account_file = os.path.join(SAVE_DIR, f"{email}_account.json")
    with open(account_file, 'w') as f:
        json.dump(account, f, indent=2)

def load_pokemon(email, slot):
    """Load Pokemon for a specific slot"""
    pokemon_file = os.path.join(SAVE_DIR, f"{email}_pokemon_slot{slot}.json")
    if os.path.exists(pokemon_file):
        with open(pokemon_file, 'r') as f:
            return json.load(f)
    return []

def save_pokemon(email, slot, pokemon_list):
    """Save Pokemon for a specific slot"""
    os.makedirs(SAVE_DIR, exist_ok=True)
    pokemon_file = os.path.join(SAVE_DIR, f"{email}_pokemon_slot{slot}.json")
    with open(pokemon_file, 'w') as f:
        json.dump(pokemon_list, f, indent=2)

def create_pokemon(species, level, shiny=0, moves=None, position=0, my_id=None):
    """Create a Pokemon dict"""
    if moves is None:
        moves = [1, 0, 0, 0]  # Default: first move only
    
    # Calculate experience (approximation based on level)
    exp = (level ** 3) if level > 1 else 0
    
    return {
        "species": species,
        "experience": exp,
        "level": level,
        "move1": moves[0] if len(moves) > 0 else 0,
        "move2": moves[1] if len(moves) > 1 else 0,
        "move3": moves[2] if len(moves) > 2 else 0,
        "move4": moves[3] if len(moves) > 3 else 0,
        "moveSelected": 1,
        "targetType": 1,
        "myID": my_id or 1,
        "position": position,
        "shiny": shiny,
        "tag": "n"
    }

def print_pokemon_list(pokemon_list):
    """Pretty print Pokemon list"""
    if not pokemon_list:
        print("  (empty)")
        return
    for p in pokemon_list:
        name = POKEMON_NAMES.get(p["species"], f"#{p['species']}")
        shiny_str = " ⭐SHINY" if p.get("shiny") == 1 else " 🌑SHADOW" if p.get("shiny") == 2 else ""
        print(f"  [{p.get('myID', '?'):3}] {name:15} Lv{p['level']:3}{shiny_str}")

def interactive_menu():
    """Main interactive menu"""
    print("\n" + "="*50)
    print("  PTD SAVE EDITOR")
    print("="*50)
    
    # List existing accounts
    if os.path.exists(SAVE_DIR):
        accounts = [f.replace("_account.json", "") for f in os.listdir(SAVE_DIR) if f.endswith("_account.json")]
        if accounts:
            print(f"\nExisting accounts: {', '.join(accounts)}")
    
    email = input("\nEnter account email (or new name to create): ").strip()
    if not email:
        print("No email entered, exiting.")
        return
    
    account = load_account(email)
    if account:
        print(f"\nLoaded account: {email}")
    else:
        print(f"\nCreating new account: {email}")
        account = {
            "trainer_id": random.randint(1000, 99999),
            "current_save": generate_save_id(),
            "password": email,
            "slots": {
                "1": {"nickname": "Satoshi", "avatar": "none", "badges": 0, "money": 50},
                "2": {"nickname": "Satoshi", "avatar": "none", "badges": 0, "money": 50},
                "3": {"nickname": "Satoshi", "avatar": "none", "badges": 0, "money": 50},
            },
            "pokedex": "0" * 151,
            "inventory": {},
            "achievements": {},
            "extraInfo": {}
        }
        save_account(email, account)
    
    while True:
        print("\n" + "-"*40)
        print("MAIN MENU")
        print("-"*40)
        print("1. Edit Slot 1")
        print("2. Edit Slot 2")
        print("3. Edit Slot 3")
        print("4. Quick Import - Full Team")
        print("5. View All Slots Summary")
        print("6. Save & Exit")
        print("0. Exit without saving")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "0":
            print("Exiting without saving changes.")
            break
        elif choice == "6":
            save_account(email, account)
            print(f"Account saved to {SAVE_DIR}")
            break
        elif choice == "5":
            for slot in ["1", "2", "3"]:
                pokemon = load_pokemon(email, slot)
                slot_data = account.get("slots", {}).get(slot, {})
                print(f"\n=== Slot {slot} ===")
                print(f"Badges: {slot_data.get('badges', 0)}, Money: ${slot_data.get('money', 50)}")
                print(f"Pokemon ({len(pokemon)}):")
                print_pokemon_list(pokemon)
        elif choice == "4":
            quick_import(email, account)
        elif choice in ["1", "2", "3"]:
            edit_slot(email, account, choice)

def edit_slot(email, account, slot):
    """Edit a specific save slot"""
    pokemon = load_pokemon(email, slot)
    slot_data = account.setdefault("slots", {}).setdefault(slot, {
        "nickname": "Satoshi", "avatar": "none", "badges": 0, "money": 50
    })
    
    while True:
        print(f"\n=== SLOT {slot} ===")
        print(f"Nickname: {slot_data.get('nickname', 'Satoshi')}")
        print(f"Badges: {slot_data.get('badges', 0)}")
        print(f"Money: ${slot_data.get('money', 50)}")
        print(f"Pokemon: {len(pokemon)}")
        print_pokemon_list(pokemon)
        
        print("\n1. Set badges")
        print("2. Set money")
        print("3. Add Pokemon")
        print("4. Add Pokemon (quick - by number)")
        print("5. Remove Pokemon")
        print("6. Clear all Pokemon")
        print("7. Import preset team")
        print("8. Back to main menu")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "8":
            save_pokemon(email, slot, pokemon)
            save_account(email, account)
            break
        elif choice == "1":
            badges = input("Enter badges (0-8): ").strip()
            try:
                slot_data["badges"] = int(badges)
            except:
                print("Invalid number")
        elif choice == "2":
            money = input("Enter money: ").strip()
            try:
                slot_data["money"] = int(money)
            except:
                print("Invalid number")
        elif choice == "3":
            add_pokemon_interactive(pokemon)
        elif choice == "4":
            add_pokemon_quick(pokemon)
        elif choice == "5":
            if pokemon:
                print("Pokemon to remove:")
                for i, p in enumerate(pokemon):
                    name = POKEMON_NAMES.get(p["species"], f"#{p['species']}")
                    print(f"  {i+1}. {name} Lv{p['level']}")
                idx = input("Enter number to remove (or 'c' to cancel): ").strip()
                if idx.lower() != 'c':
                    try:
                        pokemon.pop(int(idx) - 1)
                        # Reassign myIDs
                        for i, p in enumerate(pokemon):
                            p["myID"] = i + 1
                    except:
                        print("Invalid selection")
        elif choice == "6":
            confirm = input("Clear all Pokemon? (y/n): ").strip().lower()
            if confirm == 'y':
                pokemon.clear()
        elif choice == "7":
            import_preset_team(pokemon)

def add_pokemon_interactive(pokemon_list):
    """Add a Pokemon with full options"""
    print("\nSearch Pokemon by name or enter species number:")
    query = input("Pokemon: ").strip().lower()
    
    species = None
    if query.isdigit():
        species = int(query)
    else:
        # Search by name
        matches = [(num, name) for num, name in POKEMON_NAMES.items() if query in name.lower()]
        if len(matches) == 1:
            species = matches[0][0]
            print(f"Found: {matches[0][1]}")
        elif len(matches) > 1:
            print("Multiple matches:")
            for num, name in matches[:10]:
                print(f"  {num}: {name}")
            species = input("Enter species number: ").strip()
            species = int(species) if species.isdigit() else None
        else:
            print("No Pokemon found")
            return
    
    if not species:
        return
    
    level = input("Level (1-100): ").strip()
    level = int(level) if level.isdigit() else 5
    
    shiny = input("Shiny? (y/n): ").strip().lower()
    shiny = 1 if shiny == 'y' else 0
    
    my_id = len(pokemon_list) + 1
    poke = create_pokemon(species, level, shiny, my_id=my_id)
    pokemon_list.append(poke)
    print(f"Added {POKEMON_NAMES.get(species, f'#{species}')} Lv{level}!")

def add_pokemon_quick(pokemon_list):
    """Quick add: species level [s for shiny]"""
    print("\nQuick add format: <species#> <level> [s]")
    print("Example: 25 50 s  (Shiny Pikachu Lv50)")
    print("         6 100    (Charizard Lv100)")
    
    entry = input("Enter: ").strip().split()
    if len(entry) < 2:
        print("Need at least species and level")
        return
    
    try:
        species = int(entry[0])
        level = int(entry[1])
        shiny = 1 if len(entry) > 2 and entry[2].lower() == 's' else 0
        
        my_id = len(pokemon_list) + 1
        poke = create_pokemon(species, level, shiny, my_id=my_id)
        pokemon_list.append(poke)
        name = POKEMON_NAMES.get(species, f"#{species}")
        shiny_str = " (SHINY)" if shiny else ""
        print(f"Added {name} Lv{level}{shiny_str}!")
    except Exception as e:
        print(f"Error: {e}")

def import_preset_team(pokemon_list):
    """Import preset teams"""
    print("\nPreset Teams:")
    print("1. Starters (all 3 at Lv5)")
    print("2. Shiny Starters")
    print("3. Full Eeveelutions")
    print("4. Legendary Birds")
    print("5. Full Legendary (Birds + Mewtwo + Mew)")
    print("6. Championship Team (Lv100)")
    
    choice = input("Choice: ").strip()
    
    presets = {
        "1": [(1, 5, 0), (4, 5, 0), (7, 5, 0)],  # Starters
        "2": [(1, 5, 1), (4, 5, 1), (7, 5, 1)],  # Shiny Starters
        "3": [(133, 25, 0), (134, 25, 0), (135, 25, 0), (136, 25, 0)],  # Eeveelutions
        "4": [(144, 50, 0), (145, 50, 0), (146, 50, 0)],  # Birds
        "5": [(144, 70, 0), (145, 70, 0), (146, 70, 0), (150, 70, 0), (151, 70, 0)],  # Legendaries
        "6": [(6, 100, 0), (9, 100, 0), (3, 100, 0), (149, 100, 0), (150, 100, 0), (151, 100, 0)],  # Champs
    }
    
    if choice in presets:
        pokemon_list.clear()
        for i, (species, level, shiny) in enumerate(presets[choice]):
            poke = create_pokemon(species, level, shiny, my_id=i+1)
            pokemon_list.append(poke)
        print(f"Imported {len(pokemon_list)} Pokemon!")
    else:
        print("Invalid choice")

def quick_import(email, account):
    """Quick import to create a ready-to-play save"""
    print("\nQuick Import - Creates a complete save")
    print("1. New game (just starter)")
    print("2. Mid-game (4 badges, good team)")
    print("3. End-game (8 badges, strong team)")
    print("4. Shiny collector (various shinies)")
    
    choice = input("Choice: ").strip()
    slot = input("Slot (1/2/3): ").strip()
    if slot not in ["1", "2", "3"]:
        slot = "1"
    
    slot_data = account.setdefault("slots", {}).setdefault(slot, {})
    pokemon = []
    
    if choice == "1":
        slot_data.update({"badges": 0, "money": 500, "nickname": "Satoshi"})
        pokemon = [create_pokemon(7, 5, my_id=1)]
    elif choice == "2":
        slot_data.update({"badges": 4, "money": 25000, "nickname": "Satoshi"})
        pokemon = [
            create_pokemon(9, 36, my_id=1),   # Blastoise
            create_pokemon(25, 30, my_id=2),  # Pikachu
            create_pokemon(6, 36, my_id=3),   # Charizard
            create_pokemon(94, 30, my_id=4),  # Gengar
        ]
    elif choice == "3":
        slot_data.update({"badges": 8, "money": 100000, "nickname": "Satoshi"})
        pokemon = [
            create_pokemon(6, 80, my_id=1),   # Charizard
            create_pokemon(9, 80, my_id=2),   # Blastoise
            create_pokemon(3, 80, my_id=3),   # Venusaur
            create_pokemon(149, 75, my_id=4), # Dragonite
            create_pokemon(130, 70, my_id=5), # Gyarados
            create_pokemon(65, 70, my_id=6),  # Alakazam
        ]
    elif choice == "4":
        slot_data.update({"badges": 8, "money": 999999, "nickname": "Shiny Hunter"})
        pokemon = [
            create_pokemon(6, 100, shiny=1, my_id=1),   # Shiny Charizard
            create_pokemon(150, 100, shiny=1, my_id=2), # Shiny Mewtwo
            create_pokemon(149, 100, shiny=1, my_id=3), # Shiny Dragonite
            create_pokemon(25, 50, shiny=1, my_id=4),   # Shiny Pikachu
            create_pokemon(130, 80, shiny=1, my_id=5),  # Shiny Gyarados
            create_pokemon(151, 100, shiny=1, my_id=6), # Shiny Mew
        ]
    else:
        print("Invalid choice")
        return
    
    save_pokemon(email, slot, pokemon)
    save_account(email, account)
    print(f"\nImported to slot {slot}!")
    print(f"Badges: {slot_data.get('badges')}, Money: ${slot_data.get('money')}")
    print(f"Pokemon: {len(pokemon)}")
    print_pokemon_list(pokemon)

if __name__ == "__main__":
    interactive_menu()
