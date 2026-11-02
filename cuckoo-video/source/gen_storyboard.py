import json, sys
# (ar, en, dur) caption chunks per scene; scene visuals noted once
SCENES = [
 ("s1","hook","wide forest, push-in to the nest with three speckled eggs on the branch", "cut",
  [("في أعماق الغابة","Deep in the forest",1.5),("يبني طائرٌ صغير عشّه","a small bird builds a nest",1.7),("ثلاث بيضاتٍ مرقّطة","Three speckled eggs",1.4)]),
 ("s2","setup","cuckoo lands on the branch, red reticle on one egg, grabs it (yellow chevrons on contact)", "cut",
  [("ثم يصل الواق واق","Then a cuckoo arrives",1.4),("والأمُّ غائبة","while the mother is away",1.5),("يخطف بيضةً واحدة","It steals one egg",1.9)]),
 ("s3","build","cuckoo lays its own egg in the gap, yellow ring on the imposter egg, macro comparison", "cut",
  [("ويضع بيضته","and lays its own",1.3),("في مكانها","in its place",1.2),("تكاد تتطابق","Almost identical",1.7)]),
 ("s4","build","mother returns and sits; light sweeps day-night-day (time-lapse)", "fade",
  [("تعود الأم","The mother returns",1.3),("ولا تلاحظ شيئاً","and notices nothing",1.5),("وتمرّ الأيام","Days pass",1.6)]),
 ("s5","turn","macro: the cuckoo egg cracks and hatches first, green outline on the hatchling", "cut",
  [("يفقس الواق واق أولاً","The cuckoo hatches first",1.6),("قبل البيض الآخر","before the other eggs",1.4),("بيومٍ كامل","a full day ahead",1.6)]),
 ("s6","build","mother feeds the hatchling beak to beak; it visibly grows", "cut",
  [("تُطعمه الأم","The mother feeds it",1.4),("ظنّاً منها أنه ابنها","believing it is her own",1.7),("فيقوى ويشتدّ","and it grows strong",1.5)]),
 ("s7","turn","blind naked chick backs into an egg, cyan chevrons show the push, egg tips over the rim and falls; wide cut as it drops into the forest", "cut",
  [("ثم وهو أعمى بلا ريش","Then, still blind and naked,",1.9),("يدفع البيض الباقي","it pushes the other eggs",1.7),("بيضةً بيضة","one by one",1.4),("خارج العش","over the edge",2.2)]),
 ("s8","payoff","the chick alone in the nest grows until it dwarfs the foster mother feeding it", "cut",
  [("الآن كل الطعام له وحده","Now every meal is its alone",1.8),("يكبر ويكبر","It grows and grows",1.6),("حتى يفوق أمّه حجماً","until it dwarfs its mother",2.6)]),
 ("s9","end","the grown cuckoo spreads its wings and flies off through the light rays; the mother stays on the empty nest", "cut",
  [("وفي صباحٍ ما","And one morning",1.5),("يفرد جناحيه","it spreads its wings",1.5),("ويطير","and flies away",1.6),("ليعيد القصة من جديد","to begin the story again",3.0)]),
]
SFX = {"s2":[("thud",2.0,-10),("pop",3.9,-8)], "s3":[("thud",0.9,-10),("pop",2.3,-10)], "s5":[("click",0.9,-9),("click",1.6,-9),("pop",2.6,-8)],
       "s6":[("click",1.1,-12),("click",2.6,-12)], "s7":[("swipe",2.3,-8),("swipe",3.9,-8),("whoosh",5.3,-9),("thud",6.6,-8)], "s9":[("whoosh",3.3,-6)]}
def build(lang):
    t = 0.0; scenes = []
    for sid, role, visual, tr, chunks in SCENES:
        start = t; reads = []
        for ar, en, d in chunks:
            reads.append({"text": ar if lang == "ar" else en, "in": round(t, 2), "out": round(t + d, 2)}); t += d
        end = round(t, 2)
        scenes.append({"id": sid, "start": round(start, 2), "end": end, "beat": role, "section": "science", "sacred": False,
            "reads": reads, "visual": visual, "layout": "subject centred on a soft spotlight glow; captions centred at y 1500",
            "motion": [{"el": "cam", "what": "push-in", "t": round(start, 2), "dur": round(end - start, 2), "ease": "sineInOut"}],
            "layers": [{"name": "far", "p": 0.15, "blur": 10, "haze": 0.6}, {"name": "mid", "p": 0.4, "blur": 3, "haze": 0.3},
                       {"name": "subject", "p": 1.0, "blur": 0}, {"name": "text", "p": 1, "blur": 0}, {"name": "near", "p": 1.35, "blur": 8}],
            "transition_out": {"type": tr, "at": end, "dur": 0.5 if tr == "fade" else 0.0},
            "sfx": [{"sound": s, "at": round(start + a, 2), "gain_db": g} for s, a, g in SFX.get(sid, [])],
            "still_at": round(start + (end - start) * 0.6, 2)})
    scenes[-1].pop("transition_out")
    return {"w": 1080, "h": 1920, "fps": 60, "duration_s": round(t, 2), "lang": lang,
            "concept": "one nest, one imposter: every shot stays on the nest and what the cuckoo does to it",
            "through_object": "the speckled cuckoo egg / chick", "scenes": scenes}
for lang, path in (("ar", sys.argv[1]), ("en", sys.argv[2])):
    sb = build(lang); json.dump(sb, open(path, "w"), ensure_ascii=False, indent=1); print(lang, sb["duration_s"], "s", len(sb["scenes"]), "scenes")
