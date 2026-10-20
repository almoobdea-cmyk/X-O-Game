"""Text front-end bridge: phonemization through the JavaScript rule engine (one source of truth), plus the phone vocabulary."""
import json
import os
import subprocess
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, '..', 'cli.mjs')

# Phone inventory (matches src/phonemize.mjs); 'ː' suffix marks gemination, '_' is a pause.
BASE_PHONES = ['ʔ', 'b', 't', 'θ', 'dʒ', 'ħ', 'x', 'd', 'ð', 'r', 'z', 's', 'ʃ', 'sˤ', 'dˤ', 'tˤ', 'ðˤ', 'ʕ', 'ɣ', 'f', 'q', 'k', 'g', 'l', 'm', 'n', 'h', 'w', 'j',
               'a', 'i', 'u', 'e', 'o', 'aː', 'iː', 'uː', 'eː', 'oː', 'p', 'v', 'tʃ']
PHONES = ['<pad>', '<blank>', '_'] + BASE_PHONES + [p + 'ː' for p in BASE_PHONES if p not in ('a', 'i', 'u', 'e', 'o', 'aː', 'iː', 'uː', 'eː', 'oː')]
PHONE_TO_ID = {p: i for i, p in enumerate(PHONES)}
PAD, BLANK, PAUSE = 0, 1, 2


def phonemize_lines(lines, mode='auto'):
    """Run the JS engine on many lines at once. Returns list of {text, mode, phones, durations}."""
    if not lines:
        return []
    proc = subprocess.run(['node', CLI, 'phonemes', '--mode', mode], input='\n'.join(lines), capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


@lru_cache(maxsize=65536)
def phonemize(text, mode='auto'):
    return phonemize_lines([text], mode)[0]


def encode(phones):
    """Phone strings -> ids. Unknown phones are dropped."""
    return [PHONE_TO_ID[p] for p in phones if p in PHONE_TO_ID]


def decode(ids):
    return [PHONES[i] for i in ids if 0 <= i < len(PHONES)]
