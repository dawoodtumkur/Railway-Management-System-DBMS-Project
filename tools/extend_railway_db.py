#!/usr/bin/env python3
"""Extend railway.db with 50 new stations and 500 new trains (routes, timings,
classes, seat availability).  Existing rows are never modified.

Usage: python3 extend_railway_db.py railway.db
"""
import math, random, sqlite3, sys

SEED = 2026
N_TRAINS = {"Rajdhani": 40, "Shatabdi": 60, "Superfast": 200, "Express": 200}
JOURNEY_DATES = ["2026-11-01", "2026-11-02"]   # same dates the existing data uses
ROAD_FACTOR = 1.2                              # straight line -> rail distance

# code: (name, city, lat, lon)
EXISTING = {
    "NDLS": (28.643, 77.219), "AGC": (27.158, 77.990), "BPL": (23.267, 77.412),
    "NGP": (21.153, 79.088), "SBC": (12.978, 77.567), "MAS": (13.082, 80.275),
    "BCT": (18.969, 72.820), "ADI": (23.027, 72.601),
}
NEW = {
    "MTJ": ("Mathura Junction", "Mathura", 27.489, 77.675),
    "GWL": ("Gwalior Junction", "Gwalior", 26.215, 78.182),
    "JHS": ("Jhansi Junction", "Jhansi", 25.451, 78.568),
    "UMB": ("Ambala Cantt Junction", "Ambala", 30.349, 76.829),
    "CDG": ("Chandigarh Junction", "Chandigarh", 30.705, 76.820),
    "LDH": ("Ludhiana Junction", "Ludhiana", 30.906, 75.848),
    "ASR": ("Amritsar Junction", "Amritsar", 31.634, 74.873),
    "LKO": ("Lucknow Charbagh", "Lucknow", 26.832, 80.923),
    "CNB": ("Kanpur Central", "Kanpur", 26.453, 80.351),
    "PRYJ": ("Prayagraj Junction", "Prayagraj", 25.447, 81.827),
    "BSB": ("Varanasi Junction", "Varanasi", 25.327, 82.987),
    "DDU": ("Pt Deen Dayal Upadhyaya Junction", "Mughalsarai", 25.282, 83.119),
    "PNBE": ("Patna Junction", "Patna", 25.602, 85.138),
    "DHN": ("Dhanbad Junction", "Dhanbad", 23.795, 86.428),
    "HWH": ("Howrah Junction", "Kolkata", 22.585, 88.343),
    "BBS": ("Bhubaneswar", "Bhubaneswar", 20.250, 85.840),
    "VSKP": ("Visakhapatnam Junction", "Visakhapatnam", 17.722, 83.289),
    "RJY": ("Rajahmundry", "Rajahmundry", 17.006, 81.774),
    "BZA": ("Vijayawada Junction", "Vijayawada", 16.518, 80.620),
    "SC": ("Secunderabad Junction", "Hyderabad", 17.434, 78.501),
    "WL": ("Warangal", "Warangal", 17.973, 79.601),
    "BPQ": ("Balharshah", "Balharshah", 19.846, 79.352),
    "ET": ("Itarsi Junction", "Itarsi", 22.612, 77.762),
    "JP": ("Jaipur Junction", "Jaipur", 26.919, 75.788),
    "AII": ("Ajmer Junction", "Ajmer", 26.454, 74.640),
    "KOTA": ("Kota Junction", "Kota", 25.180, 75.860),
    "RTM": ("Ratlam Junction", "Ratlam", 23.331, 75.043),
    "BRC": ("Vadodara Junction", "Vadodara", 22.311, 73.181),
    "ST": ("Surat", "Surat", 21.205, 72.841),
    "PUNE": ("Pune Junction", "Pune", 18.529, 73.874),
    "SUR": ("Solapur", "Solapur", 17.673, 75.907),
    "GTL": ("Guntakal Junction", "Guntakal", 15.173, 77.378),
    "BSL": ("Bhusaval Junction", "Bhusawal", 21.044, 75.785),
    "NK": ("Nasik Road", "Nashik", 19.947, 73.842),
    "R": ("Raipur Junction", "Raipur", 21.256, 81.628),
    "KPD": ("Katpadi Junction", "Vellore", 12.972, 79.137),
    "SA": ("Salem Junction", "Salem", 11.668, 78.147),
    "ED": ("Erode Junction", "Erode", 11.341, 77.717),
    "CBE": ("Coimbatore Junction", "Coimbatore", 10.997, 76.967),
    "PGT": ("Palakkad Junction", "Palakkad", 10.775, 76.652),
    "TCR": ("Thrissur", "Thrissur", 10.516, 76.221),
    "ERS": ("Ernakulam Junction", "Kochi", 9.969, 76.291),
    "TVC": ("Thiruvananthapuram Central", "Thiruvananthapuram", 8.487, 76.952),
    "MDU": ("Madurai Junction", "Madurai", 9.919, 78.113),
    "TPJ": ("Tiruchirappalli Junction", "Tiruchirappalli", 10.805, 78.689),
    "TEN": ("Tirunelveli Junction", "Tirunelveli", 8.726, 77.717),
    "VM": ("Villupuram Junction", "Villupuram", 11.939, 79.492),
    "MYS": ("Mysuru Junction", "Mysuru", 12.317, 76.644),
    "MAO": ("Madgaon Junction", "Margao", 15.274, 73.958),
    "MAQ": ("Mangaluru Central", "Mangaluru", 12.867, 74.842),
}
assert len(NEW) == 50

COORD = {k: v for k, v in EXISTING.items()}
COORD.update({k: (v[2], v[3]) for k, v in NEW.items()})

# Ordered main-line corridors; trains run any sub-segment in either direction.
CORRIDORS = [
    "NDLS MTJ KOTA RTM BRC ST BCT",               # Delhi - Mumbai (via Kota)
    "NDLS JP AII ADI",                             # Delhi - Ahmedabad
    "ADI BRC ST BCT",                              # Ahmedabad - Mumbai
    "NDLS MTJ AGC GWL JHS BPL ET NGP BPQ WL SC",   # Delhi - Hyderabad
    "NDLS AGC GWL JHS BPL ET NGP BPQ WL BZA MAS",  # Delhi - Chennai
    "NDLS CNB PRYJ DDU PNBE DHN HWH",              # Delhi - Howrah
    "NDLS CNB LKO BSB PNBE",                       # Delhi - Lucknow - Patna
    "NDLS UMB LDH ASR",                            # Delhi - Amritsar
    "NDLS UMB CDG",                                # Delhi - Chandigarh
    "BCT NK BSL NGP R BBS HWH",                    # Mumbai - Howrah
    "HWH BBS VSKP RJY BZA MAS",                    # Howrah - Chennai
    "BCT PUNE SUR GTL SBC",                        # Mumbai - Bengaluru
    "BCT PUNE SUR GTL KPD MAS",                    # Mumbai - Chennai
    "BCT MAO MAQ TCR ERS TVC",                     # Konkan / Malabar
    "SC SUR PUNE BCT",                             # Hyderabad - Mumbai
    "SC GTL SBC",                                  # Hyderabad - Bengaluru
    "SC BZA MAS",                                  # Hyderabad - Chennai
    "MAS KPD SBC MYS",                             # Chennai - Bengaluru - Mysuru
    "SBC SA ED CBE PGT ERS TVC",                   # Bengaluru - Kerala
    "MAS KPD SA ED CBE PGT TCR ERS TVC",           # Chennai - Kerala
    "MAS VM TPJ MDU TEN",                          # Chennai - Madurai - Tirunelveli
]
CORRIDORS = [c.split() for c in CORRIDORS]
for c in CORRIDORS:
    for code in c:
        assert code in COORD, code


def hav(a, b):
    la1, lo1 = map(math.radians, COORD[a]); la2, lo2 = map(math.radians, COORD[b])
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(d)) * ROAD_FACTOR


CUM = []
for c in CORRIDORS:
    cum = [0.0]
    for a, b in zip(c, c[1:]):
        cum.append(cum[-1] + hav(a, b))
    CUM.append(cum)

# per-type parameters
PARAMS = {
    #            speed km/h, stop prob, halt (min), min km, max km
    "Rajdhani":  (82, 0.30, (2, 5),  900, 99999),
    "Shatabdi":  (72, 0.60, (2, 5),  150, 900),
    "Superfast": (62, 0.65, (2, 8),  250, 99999),
    "Express":   (52, 0.90, (2, 10), 150, 99999),
}
DEPART_WINDOWS = {
    "Rajdhani": [(16 * 60, 21 * 60 + 30)],
    "Shatabdi": [(5 * 60 + 15, 7 * 60 + 30), (14 * 60, 16 * 60 + 30)],
    "Superfast": [(0, 23 * 60 + 55)],
    "Express": [(0, 23 * 60 + 55)],
}
CLASS_SETS = {  # class code -> base seats
    "Rajdhani": {"3A": 300, "2A": 150, "1A": 40},
    "Shatabdi": {"3A": 140, "2A": 65},
    "Superfast": {"SL": 400, "3A": 200, "2A": 100},
    "Express": {"SL": 360, "3A": 180, "2A": 90},
}
NUMBER_POOLS = {
    "Rajdhani": range(12301, 12500),
    "Shatabdi": range(12010, 12100),
    "Superfast": range(12500, 13000),
    "Express": range(15000, 16000),
}
SUFFIX = {"Rajdhani": ["Rajdhani"], "Shatabdi": ["Shatabdi"],
          "Superfast": ["Superfast Express", "SF Express", "Superfast Mail"],
          "Express": ["Express", "Mail", "Link Express", "Intercity Express", "Passenger Express"]}

fmt = lambda m: "%02d:%02d" % ((int(m) % 1440) // 60, int(m) % 60)


def build_train(rng, ttype, city_of):
    speed, p, halt, kmin, kmax = PARAMS[ttype]
    for _ in range(1000):
        ci = rng.choices(range(len(CORRIDORS)), weights=[len(c) for c in CORRIDORS])[0]
        cor, cum = CORRIDORS[ci], CUM[ci]
        i, j = sorted(rng.sample(range(len(cor)), 2))
        if j - i < 2:
            continue
        dist = cum[j] - cum[i]
        if not (kmin <= dist <= kmax):
            continue
        idx = [i] + [k for k in range(i + 1, j) if rng.random() < p] + [j]
        if len(idx) < 3:
            idx = [i, rng.randrange(i + 1, j), j]
        if rng.random() < 0.5:
            idx = idx[::-1]
        return cor, cum, idx
    raise RuntimeError("could not build %s" % ttype)


def main(path):
    rng = random.Random(SEED)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    # --- stations
    for code, (name, city, _, _) in NEW.items():
        cur.execute("INSERT INTO stations(code,name,city) VALUES (?,?,?)", (code, name, city))
    sid = dict(cur.execute("SELECT code, station_id FROM stations"))
    cname = {code: city for code, (_, city, _, _) in NEW.items()}
    cname.update({"NDLS": "Delhi", "AGC": "Agra", "BPL": "Bhopal", "NGP": "Nagpur", "SBC": "Bengaluru",
                  "MAS": "Chennai", "BCT": "Mumbai", "ADI": "Ahmedabad"})
    cid = dict(cur.execute("SELECT code, class_id FROM classes"))
    used_no = {r[0] for r in cur.execute("SELECT train_no FROM trains")}
    used_names = {r[0] for r in cur.execute("SELECT name FROM trains")}
    pools = {t: [n for n in NUMBER_POOLS[t] if str(n) not in used_no] for t in NUMBER_POOLS}
    for t in pools:
        rng.shuffle(pools[t])

    # --- trains
    for ttype, count in N_TRAINS.items():
        for _ in range(count):
            cor, cum, idx = build_train(rng, ttype, cname)
            codes = [cor[k] for k in idx]
            # name
            o, d = cname[codes[0]], cname[codes[-1]]
            base = f"{o} {d}"
            name = None
            for suf in rng.sample(SUFFIX[ttype], len(SUFFIX[ttype])):
                cand = f"{base} {suf}"
                if cand not in used_names:
                    name = cand; break
            n = 2
            while name is None:
                cand = f"{base} {rng.choice(SUFFIX[ttype])} {n}"
                if cand not in used_names:
                    name = cand
                n += 1
            used_names.add(name)
            train_no = str(pools[ttype].pop())
            cur.execute("INSERT INTO trains(train_no,name,train_type) VALUES (?,?,?)", (train_no, name, ttype))
            tid = cur.lastrowid

            # route + timings
            speed, _, halt, _, _ = PARAMS[ttype]
            lo, hi = rng.choice(DEPART_WINDOWS[ttype])
            t = rng.randrange(lo // 5, hi // 5 + 1) * 5
            spd = speed * rng.uniform(0.92, 1.08)
            origin_pos = cum[idx[0]]
            for order, k in enumerate(idx, start=1):
                km = int(round(abs(cum[k] - origin_pos)))
                if order == 1:
                    arr, dep = None, fmt(t)
                else:
                    prev_km = int(round(abs(cum[idx[order - 2]] - origin_pos)))
                    t += (km - prev_km) / spd * 60
                    arr = fmt(t)
                    if order == len(idx):
                        dep = None
                    else:
                        t += rng.randint(*halt)
                        dep = fmt(t)
                cur.execute("INSERT INTO train_routes VALUES (?,?,?,?,?,?)",
                            (tid, sid[cor[k]], order, arr, dep, km))

            # classes + seats
            for cc, base_seats in CLASS_SETS[ttype].items():
                seats = int(round(base_seats * rng.choice([0.8, 1.0, 1.0, 1.2]) / 10)) * 10
                cur.execute("INSERT INTO train_classes VALUES (?,?,?)", (tid, cid[cc], seats))
                for dte in JOURNEY_DATES:
                    cur.execute("INSERT INTO seat_availability VALUES (?,?,?,?)",
                                (tid, dte, cid[cc], seats))
    con.commit()
    con.close()


if __name__ == "__main__":
    main(sys.argv[1])
