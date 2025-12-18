#!/usr/bin/env python3
"""
PTD1 Local Server v2 - Full Implementation
Properly handles delta saves and generates full load responses

Delta Save Format (from save_Poke):
- The game sends changes, not full data
- Each Pokemon entry has: myID, then a list of change types with data
- Change types:
  1 = needCaptured (full Pokemon data for new capture)
  2 = needLevel
  3 = needExp  
  4 = needMoves
  5 = needMoveSelected
  6 = needEvolve
  7 = needTarget
  8 = posChange
  9 = needTag
  10 = needTrade (full Pokemon data for traded Pokemon)

Full Snapshot Format (for loading):
- p1extra contains all Pokemon with full data
- Format: header_len + header + count_len + count + [pokemon_data...]
- Each Pokemon: species, exp, level, moves1-4, moveSelected, targetType, myID, pos, shiny, tag
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import os
import random
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

PORT = 8080
SAVE_DIR = "./ptd_saves"

os.makedirs(SAVE_DIR, exist_ok=True)

# =============================================================================
# PTD Encoding/Decoding
# =============================================================================

LETTER_LIST = ["m", "y", "w", "c", "q", "a", "p", "r", "e", "o"]
LETTER_TO_DIGIT = {c: str(i) for i, c in enumerate(LETTER_LIST)}
DIGIT_TO_LETTER = {str(i): c for i, c in enumerate(LETTER_LIST)}


def decode_int_string(s: str) -> int:
    """Decode PTD encoded string to integer"""
    if not s:
        return 0
    digits = ""
    for ch in s:
        if ch in LETTER_TO_DIGIT:
            digits += LETTER_TO_DIGIT[ch]
        else:
            return 0
    return int(digits) if digits else 0


def encode_int(n: int) -> str:
    """Encode integer to PTD string"""
    result = ""
    for digit in str(n):
        result += DIGIT_TO_LETTER[digit]
    return result


def read_int(blob: str, i: int) -> Tuple[int, int]:
    """Read a length-prefixed integer from blob"""
    if i >= len(blob):
        return 0, i
    length = decode_int_string(blob[i])
    i += 1
    if i + length > len(blob):
        return 0, i
    value = decode_int_string(blob[i:i+length])
    return value, i + length


def read_int2(blob: str, i: int) -> Tuple[int, int]:
    """Read a double-length-prefixed integer (for large numbers like exp)"""
    if i >= len(blob):
        return 0, i
    len_len = decode_int_string(blob[i])
    i += 1
    if i + len_len > len(blob):
        return 0, i
    length = decode_int_string(blob[i:i+len_len])
    i += len_len
    if i + length > len(blob):
        return 0, i
    value = decode_int_string(blob[i:i+length])
    return value, i + length


def encode_with_length(n: int) -> str:
    """Encode integer with single length prefix"""
    encoded = encode_int(n)
    length = encode_int(len(encoded))
    return length + encoded


def encode_with_double_length(n: int) -> str:
    """Encode integer with double length prefix (for exp, myID)"""
    encoded = encode_int(n)
    len1 = encode_int(len(encoded))
    len2 = encode_int(len(len1))
    return len2 + len1 + encoded


def read_string(blob: str, i: int) -> Tuple[str, int]:
    """Read a length-prefixed string"""
    if i >= len(blob):
        return "", i
    length = decode_int_string(blob[i])
    i += 1
    if i + length > len(blob):
        return "", i
    value = blob[i:i+length]
    return value, i + length


# =============================================================================
# ProfileID Computation
# =============================================================================

def char_to_value(c: str) -> int:
    """Convert character to numeric value for ProfileID"""
    mapping = {
        'a': 1, '1': 1, 'b': 2, '2': 2, 'c': 3, '3': 3, 'd': 4, '4': 4,
        'e': 5, '5': 5, 'f': 6, '6': 6, 'g': 7, '7': 7, 'h': 8, '8': 8,
        'i': 9, '9': 9, 'j': 10, 'k': 11, 'l': 12, 'm': 13, 'n': 14,
        'o': 15, 'p': 16, 'q': 17, 'r': 18, 's': 19, 't': 20, 'u': 21,
        'v': 22, 'w': 23, 'x': 24, 'y': 25, 'z': 26
    }
    return mapping.get(c, 0)


def num_to_letter(n: int) -> str:
    """Convert number to letter for ProfileID"""
    letters = "abcdefghijklmnopqrstuvwxyz"
    if 0 <= n < 26:
        return letters[n]
    return ""


def generate_random_save_id() -> str:
    """Generate a random 14-character save ID (alphanumeric)"""
    import string
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(14))


def compute_profile_id(current_save: str, trainer_id: int) -> Optional[str]:
    """Generate valid ProfileID matching game's numberCipher.method_137"""
    if len(current_save) != 14:
        return None
    
    char_sum = sum(char_to_value(c) for c in current_save)
    if char_sum == 0 or trainer_id < 333 or trainer_id > 99999:
        return None
    
    result = trainer_id * char_sum * 14
    result_str = str(result)
    first_digit = int(result_str[0])
    
    profile_id = ""
    for c in result_str:
        digit = int(c) + first_digit
        profile_id += num_to_letter(digit)
    
    return profile_id


# =============================================================================
# Pokemon Data Structures
# =============================================================================

def default_pokemon(poke_id: int = 1, species: int = 1, level: int = 5) -> Dict:
    """Create a default Pokemon dict"""
    return {
        "id": poke_id,
        "species": species,
        "experience": 0,
        "level": level,
        "move1": 33,  # Tackle
        "move2": 0,
        "move3": 0,
        "move4": 0,
        "moveSelected": 1,
        "targetType": 1,
        "myID": poke_id,
        "position": poke_id,
        "shiny": 0,
        "tag": ""
    }


# =============================================================================
# Delta Save Parser
# =============================================================================

def parse_delta_save(extra: str, existing_pokemon: List[Dict]) -> List[Dict]:
    """
    Parse the delta save format and apply changes to existing Pokemon list.
    
    Looking at save_Poke() in profile_user.as:
    
    Delta format structure:
    - header_len (1 char) + header (total length, skip)
    - poke_count_len (1 char) + poke_count (TOTAL pokemon, not just changed ones)
    - For each Pokemon WITH CHANGES (not all pokemon):
      - change_count_len + change_count (how many change types follow)
      - myID (double-length encoded) 
      - For each change:
        - change_type_len + change_type
        - change data (varies by type)
    
    Key insight from save_Poke: It iterates ALL pokemon but only writes entries
    for those where saveInfo.need_Save() is true. The format is:
      change_count_len + change_count + myID(double) + [changes...]
    """
    # Change type names for debugging (from JordanPlayz158's server)
    CHANGE_TYPES = {
        1: "needCaptured",
        2: "needLevel", 
        3: "needExp",
        4: "needMoves",
        5: "needMoveSelected",
        6: "needEvolve",
        7: "needTarget",
        8: "posChange",
        9: "needTag",
        10: "needTrade"
    }
    if not extra or len(extra) < 4:
        return existing_pokemon
    
    # Create lookup by myID for existing Pokemon
    pokemon_by_id = {p["myID"]: p.copy() for p in existing_pokemon}
    
    i = 0
    try:
        # Read and skip header (total length of data)
        header_len = decode_int_string(extra[i])
        i += 1 + header_len
        
        # Read total Pokemon count
        count_len = decode_int_string(extra[i])
        i += 1
        poke_count = decode_int_string(extra[i:i+count_len])
        i += count_len
        
        print(f"  Delta: total_pokemon={poke_count}, parsing changes at pos {i}...")
        
        # Parse Pokemon entries with changes
        while i < len(extra):
            start_pos = i
            
            print(f"    Parsing entry at pos {i}: {extra[i:i+20]}")
            
            # First: read change count
            change_count_len = decode_int_string(extra[i])
            i += 1
            if i + change_count_len > len(extra):
                print(f"    End of data at pos {start_pos}")
                break
            change_count = decode_int_string(extra[i:i+change_count_len])
            i += change_count_len
            
            print(f"    change_count={change_count}, now at pos {i}")
            
            if change_count == 0:
                print(f"    No changes entry at pos {start_pos}, skipping")
                continue
            
            # Then: read myID (double-length)
            print(f"    Reading myID from pos {i}: {extra[i:i+10]}")
            my_id, new_i = read_int2(extra, i)
            print(f"    myID={my_id}, advanced from {i} to {new_i}")
            i = new_i
            
            print(f"    Pokemon myID={my_id}, changes={change_count}")
            
            # Handle myID=0 (new captures without server ID yet)
            should_skip = False
            if my_id == 0:
                # Peek at first change type
                peek_i = i
                first_change_type, _ = read_int(extra, peek_i)
                
                if first_change_type == 1:  # needCaptured - valid new capture
                    max_id = max(pokemon_by_id.keys()) if pokemon_by_id else 0
                    my_id = max_id + 1
                    print(f"    myID=0 with needCaptured, assigning new myID={my_id}")
                else:
                    # Invalid entry - skip it
                    print(f"    Invalid: myID=0 with change_type={first_change_type}, skipping")
                    should_skip = True
            
            if should_skip:
                # Skip all changes in this entry
                for _ in range(change_count):
                    change_type, i = read_int(extra, i)
                    if change_type == 1:  # needCaptured
                        for _ in range(11):  # 11 fields before tag
                            _, i = read_int(extra, i) if _ not in (1, 9) else read_int2(extra, i)
                        _, i = read_string(extra, i)  # tag
                    elif change_type == 2:  # level
                        _, i = read_int(extra, i)
                    elif change_type == 3:  # exp
                        _, i = read_int2(extra, i)
                    elif change_type == 4:  # moves
                        for _ in range(4):
                            _, i = read_int(extra, i)
                    elif change_type in (5, 6, 7, 8):  # single value
                        _, i = read_int(extra, i)
                    elif change_type == 9:  # tag
                        _, i = read_string(extra, i)
                    elif change_type == 10:  # trade
                        for _ in range(10):  # 10 fields
                            _, i = read_int(extra, i) if _ not in (1,) else read_int2(extra, i)
                continue
            
            # Get or create Pokemon entry
            # IMPORTANT: Only create new Pokemon for needCaptured (type 1)
            # For other change types, the Pokemon must already exist
            if my_id not in pokemon_by_id:
                # Peek at first change type to see if this is a capture
                peek_i = i
                first_change_type, _ = read_int(extra, peek_i)
                
                if first_change_type == 1:  # needCaptured - OK to create new
                    pokemon_by_id[my_id] = default_pokemon(my_id)
                elif first_change_type == 8:  # posChange - game is reassigning myID
                    # Read the new position
                    _, temp_i = read_int(extra, peek_i)  # skip change type
                    new_position, _ = read_int(extra, temp_i)
                    
                    # Find Pokemon currently at this position and reassign its myID
                    found = False
                    for old_id, poke in list(pokemon_by_id.items()):
                        if poke.get("position") == new_position or old_id == new_position:
                            print(f"    Reassigning myID: {old_id} -> {my_id} (position {new_position})")
                            # Move to new myID
                            del pokemon_by_id[old_id]
                            poke["myID"] = my_id
                            pokemon_by_id[my_id] = poke
                            found = True
                            break
                    
                    if not found:
                        print(f"    WARNING: Could not find Pokemon for myID={my_id} posChange, skipping")
                        # Skip this change
                        _, i = read_int(extra, i)  # change type
                        _, i = read_int(extra, i)  # position
                        continue
                else:
                    # Unknown Pokemon for non-capture, non-posChange - skip
                    print(f"    WARNING: myID={my_id} not found for change_type={first_change_type}, skipping")
                    for _ in range(change_count):
                        ct, i = read_int(extra, i)
                        if ct == 2: _, i = read_int(extra, i)
                        elif ct == 3: _, i = read_int2(extra, i)
                        elif ct == 4:
                            for _ in range(4): _, i = read_int(extra, i)
                        elif ct in (5, 6, 7, 8): _, i = read_int(extra, i)
                        elif ct == 9: _, i = read_string(extra, i)
                    continue
            
            poke = pokemon_by_id[my_id]
            poke["myID"] = my_id  # Ensure myID is set
            
            # Process each change
            for change_idx in range(change_count):
                if i >= len(extra):
                    print(f"      Ran out of data at change {change_idx}")
                    break
                    
                change_type, i = read_int(extra, i)
                change_name = CHANGE_TYPES.get(change_type, f"unknown({change_type})")
                
                if change_type == 1:  # needCaptured - full new Pokemon
                    poke["species"], i = read_int(extra, i)
                    poke["experience"], i = read_int2(extra, i)
                    poke["level"], i = read_int(extra, i)
                    poke["move1"], i = read_int(extra, i)
                    poke["move2"], i = read_int(extra, i)
                    poke["move3"], i = read_int(extra, i)
                    poke["move4"], i = read_int(extra, i)
                    poke["moveSelected"], i = read_int(extra, i)
                    poke["targetType"], i = read_int(extra, i)
                    # NOTE: Delta format does NOT include inner myID (unlike snapshot format)
                    poke["position"], i = read_int(extra, i)
                    extra_rarity, i = read_int(extra, i)  # saveInfo.extra (encodes rarity)
                    poke["tag"], i = read_string(extra, i)
                    
                    # Decode rarity from extra field (JordanPlayz158's logic)
                    # This is a curveball for hackers - different species encode shiny/shadow differently
                    if extra_rarity in (1, 2, 3, 4, 5, 6, 151, 153, 168, 182, 854):
                        # Shiny Pokemon (various special values per species)
                        poke["shiny"] = 1
                    elif extra_rarity in (180, 555, 855):
                        # Shadow Pokemon
                        poke["shiny"] = 2
                    elif extra_rarity == poke["species"]:
                        # Species number matches extra = shiny
                        poke["shiny"] = 1
                    else:
                        # Normal
                        poke["shiny"] = 0
                    
                    # NOTE: We do NOT store raw extra_rarity - it's only used for shiny detection
                    # The snapshot format uses a normalized value derived from shiny status
                    
                    rarity_type = ["normal", "shiny", "shadow"][poke["shiny"]]
                    print(f"      [{change_name}] Captured: species={poke['species']}, level={poke['level']}, rarity={rarity_type} (extra={extra_rarity}), tag='{poke['tag']}'")
                    
                elif change_type == 2:  # needLevel
                    poke["level"], i = read_int(extra, i)
                    print(f"      [{change_name}] Level: {poke['level']}")
                    
                elif change_type == 3:  # needExp
                    poke["experience"], i = read_int2(extra, i)
                    print(f"      [{change_name}] Exp: {poke['experience']}")
                    
                elif change_type == 4:  # needMoves
                    poke["move1"], i = read_int(extra, i)
                    poke["move2"], i = read_int(extra, i)
                    poke["move3"], i = read_int(extra, i)
                    poke["move4"], i = read_int(extra, i)
                    print(f"      [{change_name}] Moves: {poke['move1']},{poke['move2']},{poke['move3']},{poke['move4']}")
                    
                elif change_type == 5:  # needMoveSelected
                    poke["moveSelected"], i = read_int(extra, i)
                    print(f"      [{change_name}] MoveSelected: {poke['moveSelected']}")
                    
                elif change_type == 6:  # needEvolve
                    poke["species"], i = read_int(extra, i)
                    print(f"      [{change_name}] Evolved to species: {poke['species']}")
                    
                elif change_type == 7:  # needTarget
                    poke["targetType"], i = read_int(extra, i)
                    print(f"      [{change_name}] TargetType: {poke['targetType']}")
                    
                elif change_type == 8:  # posChange
                    poke["position"], i = read_int(extra, i)
                    print(f"      [{change_name}] Position: {poke['position']}")
                    
                elif change_type == 9:  # needTag
                    poke["tag"], i = read_string(extra, i)
                    print(f"      [{change_name}] Tag: '{poke['tag']}'")
                    
                elif change_type == 10:  # needTrade - full Pokemon data (no shiny/tag)
                    poke["species"], i = read_int(extra, i)
                    poke["experience"], i = read_int2(extra, i)
                    poke["level"], i = read_int(extra, i)
                    poke["move1"], i = read_int(extra, i)
                    poke["move2"], i = read_int(extra, i)
                    poke["move3"], i = read_int(extra, i)
                    poke["move4"], i = read_int(extra, i)
                    poke["moveSelected"], i = read_int(extra, i)
                    poke["targetType"], i = read_int(extra, i)
                    poke["position"], i = read_int(extra, i)
                    print(f"      [{change_name}] Trade: species={poke['species']}, level={poke['level']}")
                
                else:
                    print(f"      [{change_name}] at pos {i}")
                    # Don't break - try to continue
        
    except Exception as e:
        print(f"  Delta parse error at pos {i}: {e}")
        import traceback
        traceback.print_exc()
    
    # Filter out invalid entries (myID=0)
    valid_pokemon = {k: v for k, v in pokemon_by_id.items() if k > 0}
    
    # Return as sorted list by position
    result = sorted(valid_pokemon.values(), key=lambda p: p.get("position", p.get("myID", 0)))
    print(f"  Final pokemon list: {len(result)} Pokemon")
    return result


# =============================================================================
# Full Snapshot Encoder
# =============================================================================

def encode_pokemon_snapshot(pokemon_list: List[Dict]) -> str:
    """
    Encode Pokemon list to p1extra format (full snapshot).
    
    Format: header_len + header + count_len + count + [pokemon_data...]
    Each Pokemon: species, exp(2), level, move1-4, moveSelected, targetType, myID(2), pos, extra_rarity, tag
    """
    if not pokemon_list:
        return "yqym"  # Empty: header_len=1, header="4", count_len=1, count=0
    
    # Build Pokemon data
    pokemon_data = ""
    for poke in pokemon_list:
        pokemon_data += encode_with_length(poke.get("species", 1))
        pokemon_data += encode_with_double_length(poke.get("experience", 0))
        pokemon_data += encode_with_length(poke.get("level", 5))
        pokemon_data += encode_with_length(poke.get("move1", 0))
        pokemon_data += encode_with_length(poke.get("move2", 0))
        pokemon_data += encode_with_length(poke.get("move3", 0))
        pokemon_data += encode_with_length(poke.get("move4", 0))
        pokemon_data += encode_with_length(poke.get("moveSelected", 1))
        pokemon_data += encode_with_length(poke.get("targetType", 1))
        pokemon_data += encode_with_double_length(poke.get("myID", 1))
        pokemon_data += encode_with_length(poke.get("position", 0))
        
        # Use stored extra_rarity if available, otherwise derive from shiny
        extra_rarity = poke.get("extra_rarity")
        if extra_rarity is None:
            # Fallback: encode shiny as extra_rarity
            shiny = poke.get("shiny", 0)
            if shiny == 1:
                extra_rarity = 1  # Generic shiny marker
            elif shiny == 2:
                extra_rarity = 180  # Generic shadow marker
            else:
                extra_rarity = 0
        pokemon_data += encode_with_length(extra_rarity)
        
        # Tag uses simple length encoding (single encoded int + raw chars)
        tag = poke.get("tag", "")
        pokemon_data += encode_int(len(tag))  # Simple length, not encode_with_length
        pokemon_data += tag
    
    # Add count
    count = len(pokemon_list)
    count_encoded = encode_int(count)
    count_len = encode_int(len(count_encoded))
    pokemon_data = count_len + count_encoded + pokemon_data
    
    # Add header (total length)
    total_len = len(pokemon_data)
    header = encode_int(total_len)
    header_len = encode_int(len(header))
    
    return header_len + header + pokemon_data


def encode_kv_blob(kv_dict: Dict) -> str:
    """Encode key-value dict to extra2/extra4 format"""
    if not kv_dict:
        return "yqym"
    
    data = ""
    count = 0
    for k, v in kv_dict.items():
        data += encode_with_length(int(k))
        data += encode_with_length(int(v))
        count += 1
    
    count_encoded = encode_int(count)
    count_len = encode_int(len(count_encoded))
    data = count_len + count_encoded + data
    
    total_len = len(data)
    header = encode_int(total_len)
    header_len = encode_int(len(header))
    
    return header_len + header + data


def parse_kv_blob(blob: str) -> Dict:
    """Parse extra2/extra4 format to key-value dict"""
    if not blob or len(blob) < 4:
        return {}
    
    result = {}
    i = 0
    try:
        header_len = decode_int_string(blob[i])
        i += 1 + header_len
        
        count_len = decode_int_string(blob[i])
        i += 1
        count = decode_int_string(blob[i:i+count_len])
        i += count_len
        
        for _ in range(count):
            k, i = read_int(blob, i)
            v, i = read_int(blob, i)
            result[k] = v
    except:
        pass
    
    return result


# =============================================================================
# Helper Functions
# =============================================================================

def safe_email(email: str) -> str:
    return email.replace("@", "_at_").replace(".", "_")


def load_account(email: str, slot: str = None) -> Tuple[Dict, List[Dict]]:
    """Load account data and Pokemon list for a specific slot"""
    se = safe_email(email)
    account_path = os.path.join(SAVE_DIR, f"{se}_account.json")
    
    account = {}
    pokemon = []
    
    if os.path.exists(account_path):
        with open(account_path, "r") as f:
            account = json.load(f)
    
    # Load slot-specific Pokemon if slot is provided
    if slot:
        pokemon_path = os.path.join(SAVE_DIR, f"{se}_pokemon_slot{slot}.json")
        if os.path.exists(pokemon_path):
            with open(pokemon_path, "r") as f:
                pokemon = json.load(f)
    
    return account, pokemon


def save_account(email: str, account: Dict, pokemon: List[Dict], slot: str = None):
    """Save account data and Pokemon list for a specific slot"""
    se = safe_email(email)
    account_path = os.path.join(SAVE_DIR, f"{se}_account.json")
    
    with open(account_path, "w") as f:
        json.dump(account, f, indent=2)
    
    # Save slot-specific Pokemon if slot is provided
    if slot:
        pokemon_path = os.path.join(SAVE_DIR, f"{se}_pokemon_slot{slot}.json")
        with open(pokemon_path, "w") as f:
            json.dump(pokemon, f, indent=2)


# =============================================================================
# HTTP Handler
# =============================================================================

class PTDHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        # Handle crossdomain.xml for Flash security policy
        if self.path == "/crossdomain.xml" or self.path.startswith("/crossdomain.xml?"):
            crossdomain = '''<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="*"/>
    <allow-http-request-headers-from domain="*" headers="*"/>
</cross-domain-policy>'''
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(crossdomain)))
            self.end_headers()
            self.wfile.write(crossdomain.encode('utf-8'))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Served crossdomain.xml")
            return
        
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"PTD Local Server v2 - Use POST")
    
    def do_POST(self):
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] POST to: {self.path}")
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(post_data)
        params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        
        action = params.get("Action", "")
        email = params.get("Email", "unknown")
        
        print(f"Action: {action}")
        print(f"Email: {email}")
        
        if action in ("loadAccount", "createAccount"):
            response = self.handle_load(params)
        elif action == "saveAccount":
            response = self.handle_save(params)
        else:
            print(f"Unknown action! Params: {params}")
            response = "Result=Failure&Reason=UnknownAction"
        
        # Toggle hex encoding - set to False to send plain text
        USE_HEX_ENCODING = False  # Try plain text first
        
        if USE_HEX_ENCODING:
            # Obfuscate response: convert to hex
            obfuscated = response.encode('utf-8').hex()
            obfuscated_bytes = obfuscated.encode('utf-8')
        else:
            # Send plain text (no hex encoding)
            obfuscated = response
            obfuscated_bytes = response.encode('utf-8')
        
        self.send_response(200)
        self.send_header("Content-Type", "application/x-www-form-urlencoded")
        self.send_header("Content-Length", str(len(obfuscated_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        if len(response) < 500:
            print(f"Response (plain): {response}")
        else:
            print(f"Response (plain): {response[:200]}...({len(response)} chars total)")
        print(f"Response ({'hex' if USE_HEX_ENCODING else 'plain'}): {obfuscated[:100]}...({len(obfuscated)} chars total)")
        self.wfile.write(obfuscated_bytes)
    
    def handle_load(self, params):
        email = params.get("Email", "unknown")
        password = params.get("Pass", "")
        action = params.get("Action", "loadAccount")
        
        # AUTO-CREATE MODE: Set to True to auto-create accounts on first login
        AUTO_CREATE = True  # Change to False to require explicit createAccount action
        
        # Password validation: Set to True to require correct password
        VALIDATE_PASSWORD = False  # Change to True to enable password checking
        
        account, _ = load_account(email)  # Just load account, not Pokemon yet
        
        if not account:
            # For createAccount OR auto-create mode, create a new account
            if action == "createAccount" or (AUTO_CREATE and action == "loadAccount"):
                print(f"Creating new account for {email} (action={action}, auto={AUTO_CREATE})")
                account = {
                    "trainer_id": random.randint(1000, 99999),
                    "current_save": generate_random_save_id(),
                    "password": password,  # Store password
                    "slots": {
                        "1": {"nickname": "Satoshi", "avatar": "none", "money": 50},
                        "2": {"nickname": "Satoshi", "avatar": "none", "money": 50},
                        "3": {"nickname": "Satoshi", "avatar": "none", "money": 50},
                    },
                    "pokedex": "0" * 151,
                    "inventory": {},
                    "achievements": {},
                    "extraInfo": {},
                }
                # Save the new account (no Pokemon yet)
                save_account(email, account, [], "1")
                return self.build_load_response(email, account)
            else:
                print("No account found, returning failure")
                return "Result=Failure&Reason=NotFound"
        
        # Validate password if enabled
        if VALIDATE_PASSWORD:
            stored_password = account.get("password", "")
            if stored_password and password != stored_password:
                print(f"Password mismatch for {email}")
                return "Result=Failure&Reason=WrongPass"
        
        return self.build_load_response(email, account)
    
    def handle_save(self, params):
        email = params.get("Email", "unknown")
        save_string = params.get("saveString", "")
        
        # Save raw for debugging
        se = safe_email(email)
        with open(os.path.join(SAVE_DIR, f"{se}_raw_save.txt"), "w") as f:
            f.write(save_string)
        
        # Parse save string
        save_data = dict(p.split("=", 1) for p in save_string.split("&") if "=" in p)
        
        # Log all save fields for debugging
        print(f"Save data fields:")
        for key, value in sorted(save_data.items()):
            if key in ('extra', 'extra2', 'extra3', 'extra4', 'pokedex'):
                print(f"  {key}: ({len(value)} chars)")
            else:
                print(f"  {key}: {value}")
        
        slot = save_data.get("num", "1")
        is_new_game = save_data.get("newGame") == "yes"
        
        print(f"Slot: {slot}, NewGame: {is_new_game}")
        print(f"Extra length: {len(save_data.get('extra', ''))}")
        
        # Load existing data (account + slot-specific Pokemon)
        account, pokemon = load_account(email, slot)
        
        # If starting a new game in this slot, clear the Pokemon for this slot
        if is_new_game:
            pokemon = []
            print(f"New game in slot {slot}, clearing Pokemon")
        
        if not account:
            account = {
                "trainer_id": random.randint(1000, 99999),
                "current_save": generate_random_save_id(),
                "slots": {},
                "pokedex": "0" * 151,
                "inventory": {},
                "achievements": {},
                "extraInfo": {},
            }
            print(f"Created new account with save ID: {account['current_save']}")
        
        # Update slot data
        account["slots"] = account.get("slots", {})
        account["slots"][slot] = {
            "nickname": save_data.get("nickname", "Satoshi"),
            "avatar": save_data.get("avatar", "none"),
            "badges": int(save_data.get("badges", "0")),
            "money": int(save_data.get("money", "50")),
            "version": int(save_data.get("version", "0")),
            "advanced": int(save_data.get("advanced", "0")),
            "advanced_a": int(save_data.get("advanced_a", "0")),
            "classic": int(save_data.get("classic", "0")),
            "challenge": int(save_data.get("challenge", "0")),
        }
        
        # Update pokedex
        if save_data.get("pokedex"):
            account["pokedex"] = save_data["pokedex"]
        
        # Update inventory
        if save_data.get("extra2"):
            account["inventory"] = parse_kv_blob(save_data["extra2"])
        
        # Update achievements
        if save_data.get("extra3"):
            account["achievements"] = parse_kv_blob(save_data["extra3"])
        
        # Update extraInfo
        if save_data.get("extra4"):
            account["extraInfo"] = parse_kv_blob(save_data["extra4"])
        
        # Parse Pokemon delta and apply to existing list
        extra = save_data.get("extra", "")
        print(f"Parsing delta: {extra[:50]}..." if len(extra) > 50 else f"Parsing delta: {extra}")
        
        try:
            pokemon = parse_delta_save(extra, pokemon)
        except Exception as e:
            print(f"ERROR parsing delta: {e}")
            print(f"Keeping existing Pokemon list ({len(pokemon)} Pokemon)")
            # Don't update pokemon list if parsing fails
        
        print(f"Pokemon after delta: {len(pokemon)}")
        for p in pokemon:
            print(f"  - #{p.get('species')} Lv{p.get('level')} (myID={p.get('myID')})")
        
        # Save everything (account + slot-specific Pokemon)
        save_account(email, account, pokemon, slot)
        
        # Build response
        response = f"Result=Success&newSave={account['current_save']}"
        
        # Include newPokePos for new Pokemon (the game needs these to assign IDs)
        for poke in pokemon:
            pos = poke.get("position", poke.get("myID", 1))
            my_id = poke.get("myID", pos)
            response += f"&newPokePos_{pos}={my_id}"
        
        return response
    
    def build_load_response(self, email: str, account: Dict) -> str:
        trainer_id = account.get("trainer_id", 1234)
        current_save = account.get("current_save", "abcdefghijklmn")
        profile_id = compute_profile_id(current_save, trainer_id)
        
        print(f"Building load response: TrainerID={trainer_id}, ProfileID={profile_id}")
        
        # Load Pokemon for each slot
        _, pokemon1 = load_account(email, "1")
        _, pokemon2 = load_account(email, "2")
        _, pokemon3 = load_account(email, "3")
        
        print(f"Pokemon counts: slot1={len(pokemon1)}, slot2={len(pokemon2)}, slot3={len(pokemon3)}")
        
        # Build p1extra (slot 1)
        p1extra = encode_pokemon_snapshot(pokemon1)
        print(f"Encoded p1extra ({len(p1extra)} chars): {p1extra[:80]}..." if len(p1extra) > 80 else f"Encoded p1extra: {p1extra}")
        
        # Build extra2 (inventory)
        p1extra2 = encode_kv_blob(account.get("inventory", {}))
        
        # Build extra3 (achievements)
        p1extra3 = encode_kv_blob(account.get("achievements", {}))
        
        # Build extra4 (extraInfo)
        p1extra4 = encode_kv_blob(account.get("extraInfo", {}))
        
        # Get slot data
        slots = account.get("slots", {})
        slot1 = slots.get("1", {})
        slot2 = slots.get("2", {})
        slot3 = slots.get("3", {})
        
        pc1 = len(pokemon1)  # Pokemon count for slot 1
        pc2 = len(pokemon2)  # Pokemon count for slot 2
        pc3 = len(pokemon3)  # Pokemon count for slot 3
        
        # Build slot 2 and 3 extras
        p2extra = encode_pokemon_snapshot(pokemon2)
        p3extra = encode_pokemon_snapshot(pokemon3)
        
        # Build response
        parts = [
            "Result=Success",
            "Reason=LoggedIn",
            f"CurrentSave={current_save}",
            f"newSave={current_save}",
            f"TrainerID={trainer_id}",
            f"ProfileID={profile_id}",
            f"pokedex={account.get('pokedex', '0' * 151)}",
            
            # Slot 1
            f"nickname1={slot1.get('nickname', 'Satoshi')}",
            f"avatar1={slot1.get('avatar', 'none')}",
            f"advanced1={slot1.get('advanced', 0)}",
            f"advanced_a1={slot1.get('advanced_a', 0)}",
            f"classic1={slot1.get('classic', 0)}",
            f"challenge1={slot1.get('challenge', 0)}",
            f"badges1={slot1.get('badges', 0)}",
            f"money1={slot1.get('money', 50)}",
            f"version1={slot1.get('version', 0)}",
            f"PC1={pc1}",
            f"p1extra={p1extra}",
            f"p1extra2={p1extra2}",
            f"p1extra3={p1extra3}",
            f"p1extra4={p1extra4}",
        ]
        
        # Add Pokemon names for slot 1
        for i, poke in enumerate(pokemon1):
            tag = poke.get("tag", f"Pokemon{i+1}")
            parts.append(f"p1PN{i+1}={tag}")
        
        # Slot 2
        parts.extend([
            f"nickname2={slot2.get('nickname', 'Satoshi')}",
            f"avatar2={slot2.get('avatar', 'none')}",
            f"advanced2={slot2.get('advanced', 0)}",
            f"advanced_a2={slot2.get('advanced_a', 0)}",
            f"classic2={slot2.get('classic', 0)}",
            f"challenge2={slot2.get('challenge', 0)}",
            f"badges2={slot2.get('badges', 0)}",
            f"money2={slot2.get('money', 50)}",
            f"version2={slot2.get('version', 0)}",
            f"PC2={pc2}",
            f"p2extra={p2extra}",
            "p2extra2=yqym",
            "p2extra3=yqym",
            "p2extra4=yqym",
        ])
        
        # Add Pokemon names for slot 2
        for i, poke in enumerate(pokemon2):
            tag = poke.get("tag", f"Pokemon{i+1}")
            parts.append(f"p2PN{i+1}={tag}")
        
        # Slot 3
        parts.extend([
            f"nickname3={slot3.get('nickname', 'Satoshi')}",
            f"avatar3={slot3.get('avatar', 'none')}",
            f"advanced3={slot3.get('advanced', 0)}",
            f"advanced_a3={slot3.get('advanced_a', 0)}",
            f"classic3={slot3.get('classic', 0)}",
            f"challenge3={slot3.get('challenge', 0)}",
            f"badges3={slot3.get('badges', 0)}",
            f"money3={slot3.get('money', 50)}",
            f"version3={slot3.get('version', 0)}",
            f"PC3={pc3}",
            f"p3extra={p3extra}",
            "p3extra2=yqym",
            "p3extra3=yqym",
            "p3extra4=yqym",
        ])
        
        # Add Pokemon names for slot 3
        for i, poke in enumerate(pokemon3):
            tag = poke.get("tag", f"Pokemon{i+1}")
            parts.append(f"p3PN{i+1}={tag}")
        
        return "&".join(parts)
    
    def log_message(self, format, *args):
        pass  # Quiet logging


# =============================================================================
# Main
# =============================================================================

def main():
    # Test encoding
    print("Testing encoding...")
    test_pokemon = [
        {"species": 1, "experience": 0, "level": 5, "move1": 33, "move2": 45, 
         "move3": 0, "move4": 0, "moveSelected": 1, "targetType": 1, 
         "myID": 1, "position": 1, "shiny": 0, "tag": "Bulbasaur"}
    ]
    encoded = encode_pokemon_snapshot(test_pokemon)
    print(f"Test encode: {encoded}")
    print()
    
    print(f"PTD Local Server v2 starting on port {PORT}")
    print(f"Saves will be stored in: {os.path.abspath(SAVE_DIR)}")
    print(f"\nWaiting for connections...\n")
    
    server = HTTPServer(("0.0.0.0", PORT), PTDHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
