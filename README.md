# PTD1 Local Server & Save Editor

A bare-minimum implementation to enable fully local/offline play of Pokemon Tower Defense 1. This project provides a local save server and save editor that work with the original PTD1 SWF file.

## Overview

The original PTD1 game required connection to SnD servers for saving/loading progress. Those servers have been shut down for years, and only community-run fan servers exist today. This project provides a fully local alternative:

- **Local Save Server** (`ptd_server_v2.py`) - Handles all save/load requests locally
- **Save Editor** (`ptd_save_editor.py`) - Create and modify save files directly

No internet connection or external servers required.

## Requirements

- Python 3.6+
- A Flash player (e.g., [FlashArch](https://flasharch.com/), Ruffle, or Flashpoint)
- A modified PTD1 SWF file (included in this repo)

## Quick Start

### 1. Start the Local Server

```bash
python ptd_server_v2.py
```

The server runs on port 8080 by default. You should see:
```
PTD Local Server v2 starting on port 8080
Saves will be stored in: ~/ptd_saves
Waiting for connections...
```

### 2. Play the Game

Open the included modified PTD1 SWF in your Flash player. The game defaults to connecting to `localhost:8080`. 

To connect to a different server, use the options menu from the game's home screen.

### 3. Create an Account

Create an account or log in - all data is saved locally to `./ptd_saves/` (in the same folder as the server script).

### How It Works

The server intercepts save requests from the game and stores data as JSON files:

```
./ptd_saves/
  {email}_account.json       # Account data, trainer ID, slot metadata
  {email}_pokemon_slot1.json # Slot 1 Pokemon
  {email}_pokemon_slot2.json # Slot 2 Pokemon
  {email}_pokemon_slot3.json # Slot 3 Pokemon
  {email}_raw_save.txt       # Debug: last raw save string
```

The `ptd_saves` folder is created in the same directory where you run the server, making it portable and easy to back up.

### Configuration

Edit these variables at the top of `ptd_server_v2.py`:

```python
USE_HEX_ENCODING = False  # Must be False for standard Flash players
AUTO_CREATE = True        # Auto-create accounts on login attempt
VALIDATE_PASSWORD = False # Skip password validation
```

### Limitations

This is a minimal implementation focused on single-player functionality:

- No trading between accounts
- No online leaderboards
- No daily/weekly  gifts challenges requiring server validation


## Save Editor
Mostly for testing purposes
### Features

- Create new accounts
- Edit badges, money, nickname
- Add/remove Pokemon
- Set Pokemon level, species, shiny status
- Import preset teams
- Quick-create endgame saves for testing

### Usage

```bash
python ptd_save_editor.py
```

### Quick Add Pokemon

Use the quick add format: `<species#> <level> [s]`

```
25 50 s   → Shiny Pikachu Lv50
6 100     → Charizard Lv100
150 70 s  → Shiny Mewtwo Lv70
```

### Preset Teams

The editor includes preset teams for quick setup:

1. **Starters** - Bulbasaur, Charmander, Squirtle (Lv5)
2. **Shiny Starters** - Same but shiny
3. **Eeveelutions** - Eevee + evolutions (Lv25)
4. **Legendary Birds** - Articuno, Zapdos, Moltres (Lv50)
5. **Full Legendary** - Birds + Mewtwo + Mew (Lv70)
6. **Championship** - Fully evolved starters + Dragonite + Mewtwo + Mew (Lv100)

### Quick Import

Option 4 in the main menu creates complete saves:

- **New game** - Fresh start with one starter
- **Mid-game** - 4 badges, solid team
- **End-game** - 8 badges, strong Pokemon
- **Shiny collector** - 8 badges, all shiny team

## Pokemon Species Reference

Common species numbers:

| # | Pokemon | # | Pokemon | # | Pokemon |
|---|---------|---|---------|---|---------|
| 1 | Bulbasaur | 7 | Squirtle | 25 | Pikachu |
| 4 | Charmander | 6 | Charizard | 9 | Blastoise |
| 3 | Venusaur | 150 | Mewtwo | 151 | Mew |
| 144 | Articuno | 145 | Zapdos | 146 | Moltres |
| 149 | Dragonite | 130 | Gyarados | 143 | Snorlax |
| 94 | Gengar | 65 | Alakazam | 68 | Machamp |

## Troubleshooting

### "Connection failed" or can't log in

1. Ensure the server is running on port 8080
2. Check that the game is pointing to the correct server (Options menu)
3. Some Flash players need to allow local network connections

### "Suspected of hacking" error

This usually means Pokemon data is corrupted. Solutions:
- Delete the affected save files in `~/ptd_saves/`
- Use the save editor to create a fresh save
- Check server logs for parsing errors

### Pokemon not saving

- Ensure the server is running when you save
- Check server console for error messages
- Verify save files are being created in `./ptd_saves/`


## Credits ##

- Original game by Sam & Dan Games
- Encoding research based on work by JordanPlayz158
- This implementation is for preservation and offline play purposes

## Disclaimer

This project is for educational and preservation purposes. Pokemon Tower Defense was created by Sam & Dan Games. With the official servers long gone, this implementation allows the game to be played fully offline without relying on fan servers.
