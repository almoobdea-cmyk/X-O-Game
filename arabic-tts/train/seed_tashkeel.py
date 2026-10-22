"""Seed step for the diacritizer: label a corpus once with the tashkeel skill prompt (Claude), then train the
self-contained diacritizer on the result. Used at data-preparation time only; the trained TTS never calls Claude.

  python seed_tashkeel.py --in data/metadata.jsonl --out data/metadata.vocalized.jsonl --corpus data/diacritized.txt [--mode saudi] [--limit 5000]

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile). Lines already carrying marks are kept as they are.
"""
import argparse
import json
import os
import re
import sys

import anthropic

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, '..', '..', '.claude', 'skills', 'arabic-harakat-reading', 'assets')
MARK_RE = re.compile(r'[ً-ْٰ]')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True); ap.add_argument('--corpus', required=True)
    ap.add_argument('--mode', default='saudi', choices=['saudi', 'fusha']); ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--batch', type=int, default=25); ap.add_argument('--model', default='claude-opus-5-5')
    args = ap.parse_args()
    prompt = open(os.path.join(SKILL, 'prompt-saudi.md' if args.mode == 'saudi' else 'prompt.md'), encoding='utf-8').read()
    instructions = prompt[:prompt.index('صيغة الإخراج:')] + (
        'صيغة الإخراج: أجب بمصفوفة JSON واحدة من السلاسل النصية بالترتيب، كلّ سلسلة هي الجملة المقابلة مشكّلة تشكيلًا كاملًا بالاصطلاح أعلاه، بلا أي نص آخر.\n\nالجمل:\n')
    client = anthropic.Anthropic()
    items = [json.loads(l) for l in open(args.inp, encoding='utf-8') if l.strip()]
    if args.limit:
        items = items[:args.limit]
    done = 0
    with open(args.out, 'w', encoding='utf-8') as out, open(args.corpus, 'a', encoding='utf-8') as corpus:
        for i in range(0, len(items), args.batch):
            chunk = items[i:i + args.batch]
            todo = [it for it in chunk if not MARK_RE.search(it['text'])]
            if todo:
                listing = '\n'.join(f'{k + 1}. {it["text"]}' for k, it in enumerate(todo))
                resp = client.messages.create(model=args.model, max_tokens=16000, output_config={'effort': 'medium'},
                                              messages=[{'role': 'user', 'content': instructions + listing + '\n'}])
                if resp.stop_reason == 'refusal':
                    print('refused batch', i, file=sys.stderr); continue
                raw = ''.join(b.text for b in resp.content if b.type == 'text')
                arr = json.loads(raw[raw.index('['):raw.rindex(']') + 1])
                if len(arr) != len(todo):
                    print(f'batch {i}: got {len(arr)} for {len(todo)} lines, skipped', file=sys.stderr); continue
                for it, voc in zip(todo, arr):
                    it['text_raw'] = it['text']; it['text'] = voc
            for it in chunk:
                out.write(json.dumps(it, ensure_ascii=False) + '\n')
                if MARK_RE.search(it['text']):
                    corpus.write(it['text'] + '\n'); done += 1
    print(f'vocalized {done} of {len(items)} lines -> {args.out}; corpus appended at {args.corpus}')


if __name__ == '__main__':
    main()
