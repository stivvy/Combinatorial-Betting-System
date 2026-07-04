#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — PHASE 2: WHEEL ENGINE  v8.0
 Probability-Proportional Sampling + Greedy Set Cover

 THE FUNDAMENTAL FIX:
   Previous versions picked the most likely outcome per game
   then tried to "inject" draws as an afterthought. This
   produced tickets with 0-1 draws when reality has 4-5.

   Root cause: treating 15 games independently instead of as
   a joint probability problem.

   Correct approach: PROBABILITY-PROPORTIONAL SAMPLING.
   Each game contributes outcome "1", "X", or "2" to a ticket
   with exactly the probability the odds imply. No forcing,
   no injection, no minimum counts. A game with 29% draw
   probability will contribute a draw to ~29% of tickets
   automatically — because that's what the maths says.

   This produces the correct draw distribution (~4 draws per
   15-game jackpot) emerging naturally from the probabilities,
   not forced by arbitrary rules.

 Then: Greedy Set Cover selects tickets from this pool that
 collectively cover all worst-case scenarios within the budget.
================================================================
"""
import json, argparse, sys, os, csv, random, math
from itertools import combinations as icomb
from datetime import datetime

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

TICKET_COST = 15
ALL_OUTCOMES = ["1", "X", "2"]

def banner():
    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║   PHASE 2: WHEEL ENGINE v8  |  Prob-Proportional        ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(t=""):
    if t: print(f"{C.CY}{C.B}  -- {t} {'-'*(54-len(t))}{C.R}")
    else: print(f"{C.GY}  {'-'*58}{C.R}")

# ── PROBABILITY-PROPORTIONAL CANDIDATE POOL ──────────────────

def build_candidate_pool(all_results: list, max_candidates: int = 1000) -> list:
    """
    Generate candidate tickets by sampling from the true probability
    distribution of each game.

    For each game, the probability of picking outcome o is exactly
    P(o) as implied by the odds — not the binary most-likely-pick.

    This means:
      - A 40% home / 29% draw / 31% away game contributes:
          "1" to ~40% of tickets
          "X" to ~29% of tickets
          "2" to ~31% of tickets
      - Across 15 games, the draw distribution emerges correctly
        (~4.2 draws per ticket on average) WITHOUT any forcing.

    We generate a large pool (1000 tickets) so the greedy cover
    has enough diversity to work with.
    """
    total_games = len(all_results)
    seen = set()
    cand = []

    def add(t):
        tt = tuple(t)
        if tt not in seen:
            seen.add(tt)
            cand.append(tt)

    rng = random.Random(42)

    # Get per-game probability vectors
    probs = []
    for r in all_results:
        ph = float(r.get("p_home") or 0.33)
        px = float(r.get("p_draw") or 0.33)
        pa = float(r.get("p_away") or 0.33)
        # Normalise in case of rounding
        total = ph + px + pa
        probs.append((ph/total, px/total, pa/total))

    attempts = 0
    while len(cand) < max_candidates and attempts < max_candidates * 5:
        attempts += 1
        ticket = []
        for ph, px, pa in probs:
            r = rng.random()
            if r < ph:
                ticket.append("1")
            elif r < ph + px:
                ticket.append("X")
            else:
                ticket.append("2")
        add(ticket)

    return cand

# ── SCENARIO BUILDER ─────────────────────────────────────────

def build_scenarios(all_results: list, need: int) -> list:
    """
    Build worst-case scenarios: subsets of games where the
    probability-weighted pick is wrong.

    Each scenario represents 'need_wrong' games going to their
    most likely alternative outcome. The wheel must have at
    least one ticket scoring >= need on every scenario.
    """
    total_games = len(all_results)
    num_wrong   = max(0, total_games - need)

    # Base ticket = most likely outcome per game
    base = []
    for r in all_results:
        ph = float(r.get("p_home") or 0.33)
        px = float(r.get("p_draw") or 0.33)
        pa = float(r.get("p_away") or 0.33)
        if ph >= px and ph >= pa:   base.append("1")
        elif px >= ph and px >= pa: base.append("X")
        else:                        base.append("2")

    # Rank games by confidence (least confident first = most likely to be wrong)
    confidence = []
    for i, r in enumerate(all_results):
        ph = float(r.get("p_home") or 0.33)
        px = float(r.get("p_draw") or 0.33)
        pa = float(r.get("p_away") or 0.33)
        confidence.append((i, max(ph, px, pa)))
    confidence.sort(key=lambda x: x[1])  # least confident first

    # Build scenarios by flipping the num_wrong least confident games
    scenarios = []
    for wrong_set in icomb(range(total_games), num_wrong):
        scenario = list(base)
        for wi in wrong_set:
            # Flip to most likely alternative
            ph = float(all_results[wi].get("p_home") or 0.33)
            px = float(all_results[wi].get("p_draw") or 0.33)
            pa = float(all_results[wi].get("p_away") or 0.33)
            ranked = sorted([("1",ph),("X",px),("2",pa)], key=lambda x:x[1], reverse=True)
            primary = ranked[0][0]
            scenario[wi] = ranked[1][0]  # second most likely
        scenarios.append(tuple(scenario))

    return scenarios

def score(t, s):
    return sum(1 for a, b in zip(t, s) if a == b)

# ── GREEDY SET COVER ─────────────────────────────────────────

def greedy_cover(cand, scen, target, maxt):
    """
    Standard greedy set cover on the probability-proportional pool.
    Selects tickets that collectively cover all scenarios.
    """
    unc  = set(range(len(scen)))
    sel  = []
    used = set()

    while unc and len(sel) < maxt:
        bci = -1; bc = -1; bcov = set()
        for ci, c in enumerate(cand):
            if ci in used: continue
            cov = {si for si in unc if score(c, scen[si]) >= target}
            if len(cov) > bc:
                bc = len(cov); bci = ci; bcov = cov
        if bci == -1 or bc == 0: break
        sel.append(cand[bci]); used.add(bci); unc -= bcov

    return sel

# ── DIVERSITY FILL ────────────────────────────────────────────

def diversity_fill(sel, cand, maxt, all_results):
    """
    Fill remaining budget with tickets from the probability-proportional
    pool ranked by diversity from already-selected tickets.

    Because the pool itself was generated proportionally, the fill
    tickets also have correct draw distributions — no forcing needed.
    """
    total_games = len(all_results)
    probs_list  = []
    for r in all_results:
        ph = float(r.get("p_home") or 0.33)
        px = float(r.get("p_draw") or 0.33)
        pa = float(r.get("p_away") or 0.33)
        t  = ph + px + pa
        probs_list.append({"1": ph/t, "X": px/t, "2": pa/t})

    def logprob(c):
        return sum(math.log(max(probs_list[i].get(p, 0.01), 0.01))
                   for i, p in enumerate(c))

    def div(c):
        if not sel: return 0
        return sum(sum(1 for a, b in zip(c, s) if a != b)
                   for s in sel) / (len(sel) * len(c))

    from itertools import groupby as _gb

    # Pre-build the dynamic max_run constraint
    def max_run_of(ticket):
        return max(len(list(g)) for _, g in _gb(ticket)) if ticket else 0

    # Constraint: reject tickets Phase 3 would certainly reject
    def passes_basic(c):
        full = list(c)
        h = full.count("1"); d = full.count("X")
        # Hard limits: too many home wins OR zero draws is historically wrong
        if h > 13: return False
        if d == 0 and total_games >= 13: return False
        # Consecutive run limit
        mr = max_run_of(full)
        if mr > 8: return False
        return True

    ss      = set(tuple(s) for s in sel)
    rem     = [c for c in cand if tuple(c) not in ss and passes_basic(c)]
    lps     = [logprob(c) for c in rem]
    lp_min  = min(lps) if lps else 0
    lp_rng  = (max(lps) - lp_min) if lps else 1

    def combined(ic):
        i, c = ic
        pn = (lps[i] - lp_min) / (lp_rng or 1)
        return 0.5 * pn + 0.5 * div(c)

    ranked = sorted(enumerate(rem), key=combined, reverse=True)
    for _, c in ranked:
        if len(sel) >= maxt: break
        if not any(all(a == b for a, b in zip(c, s)) for s in sel):
            sel.append(c)

    return sel

# ── EV CALCULATION ────────────────────────────────────────────

PRIZE_TABLE = {15: 15_000_000, 14: 1_000_000, 13: 125_000, 12: 15_000}

def estimate_ev(full, all_results):
    gp = {}
    for r in all_results:
        g = r["game"] - 1
        gp[g] = {"1": float(r.get("p_home") or .33),
                 "X": float(r.get("p_draw") or .33),
                 "2": float(r.get("p_away") or .33)}
    ev = 0.0
    for t in full:
        pc = [gp.get(g, {"1":.33,"X":.33,"2":.33}).get(p, .33)
              for g, p in enumerate(t)]
        dp = [0.0]*16; dp[0] = 1.0
        for p in pc:
            nd = [0.0]*16
            for s in range(16):
                if dp[s] == 0: continue
                nd[s]   += dp[s] * (1-p)
                if s<15: nd[s+1] += dp[s] * p
            dp = nd
        for sc, pr in PRIZE_TABLE.items():
            ev += dp[sc] * pr
    cost = len(full) * TICKET_COST
    return {"ev": round(ev,2), "cost": cost,
            "roi": round((ev-cost)/cost*100,2) if cost else 0}

# ── ASSEMBLE (bankers + uncertain) ────────────────────────────

def assemble(tickets, bankers, total_games):
    """Merge banker picks into full tickets."""
    if not bankers:
        return [list(t) for t in tickets]
    bp = {b["game"]-1: b["banker_pick"] for b in bankers}
    full = []
    for ut in tickets:
        f = []; pos = 0
        for i in range(total_games):
            if i in bp: f.append(bp[i])
            else: f.append(ut[pos]); pos += 1
        full.append(f)
    return full

# ── DISPLAY ───────────────────────────────────────────────────

def print_draw_distribution(full, exp_draws):
    from collections import Counter
    dc = Counter(t.count("X") for t in full)
    print(f"  {C.GY}Draw distribution (expected ~{exp_draws:.1f} from odds):{C.R}")
    for k in sorted(dc.keys()):
        bar = "#" * dc[k]
        print(f"    {k} draws: {dc[k]:>3} tickets  {C.CY}{bar}{C.R}")
    actual_mean = sum(t.count("X") for t in full) / len(full) if full else 0
    print(f"  {C.GY}Mean draws in tickets: {actual_mean:.2f} | Expected: {exp_draws:.2f}{C.R}\n")

def print_summary(full, bankers, total_games, ev, target, need, exp_draws):
    sep("WHEEL SUMMARY"); print()
    print(f"  {C.GR}{C.B}╔══ RESULT ═══════════════════════════════════════════════╗{C.R}")
    rows = [("Bankers locked",    f"{len(bankers)} games"),
            ("Total games",       f"{total_games}"),
            ("Tickets generated", f"{len(full)}"),
            ("Total cost",        f"KES {ev['cost']}"),
            ("Target guarantee",  f">= {target}/{total_games}"),
            ("Expected draws",    f"~{exp_draws:.1f} (from odds)"),
            ("Mean draws/ticket", f"{sum(t.count('X') for t in full)/len(full):.2f}"),
            ("Expected value",    f"KES {ev['ev']:,.0f}"),
            ("Expected ROI",      f"{ev['roi']:+.1f}%")]
    for l, v in rows:
        col = C.GR if "ROI" in l and ev["roi"]>=0 else (C.RE if "ROI" in l else C.YE)
        print(f"  {C.GR}║ {C.R}{l:<28}{col}{v:>26}{C.R}{C.GR} ║{C.R}")
    print(f"  {C.GR}╚═══════════════════════════════════════════════════════╝{C.R}\n")
    print_draw_distribution(full, exp_draws)

def print_tickets(full, bankers, total_games):
    sep("BETTING SLIPS")
    bi = {b["game"]-1 for b in bankers}
    print(f"\n  {C.GY}Key: {C.GR}Green{C.GY}=banker | {C.YE}Yellow{C.GY}=uncertain | (nX)=draw count{C.R}\n")
    for i, t in enumerate(full):
        d = t.count("X")
        print(f"  {C.CY}Slip {i+1:>3}{C.R}: ", end="")
        for g, p in enumerate(t):
            col = C.GR+C.B if g in bi else C.YE
            print(f"{col}{p}{C.R}", end="")
            if g < total_games-1: print(f"{C.GY}-{C.R}", end="")
        print(f"  {C.GY}({d}X){C.R}")
    print()

def save_tickets(full, ev, bankers, total_games, target, need):
    with open("wheel_tickets.json","w",encoding="utf-8") as f:
        json.dump({"generated":datetime.now().isoformat(),
                   "num_tickets":len(full),"total_cost_kes":ev["cost"],
                   "expected_value_kes":ev["ev"],"expected_roi_pct":ev["roi"],
                   "bankers_locked":len(bankers),"total_games":total_games,
                   "target_score":target,"num_correct_needed":need,
                   "tickets":full},f,indent=2)
    with open("sms_slips.txt","w",encoding="utf-8") as f:
        f.write(f"JACKPOT SLIPS\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{len(full)} x KES {TICKET_COST} = KES {ev['cost']}\n\n")
        if bankers:
            f.write("BANKERS:\n")
            for b in bankers:
                c = b.get("confidence")
                cs = f"{float(c):.1f}%" if isinstance(c,(int,float)) else "?"
                f.write(f"  G{b['game']:>2}: {b['home']:<20} vs {b['away']:<20}"
                        f" -> {b['banker_pick']} ({cs})\n")
        f.write(f"\nSMS (send to 29090):\n{'-'*44}\n")
        for i,t in enumerate(full):
            f.write(f"Slip {i+1:>3}: JP#{''.join(t)}\n")
    with open("wheel_tickets.csv","w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"G{i+1}" for i in range(total_games)]+["Draws","SMS"])
        for t in full:
            w.writerow(t+[t.count("X"),"JP#"+''.join(t)])
    print(f"  {C.GR}OK wheel_tickets.json | sms_slips.txt | wheel_tickets.csv{C.R}")
    print(f"  {C.CY}  Next: python phase3_filter.py{C.R}\n")

# ── MAIN ─────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--budget",      type=int, default=500)
    p.add_argument("--target",      type=int, default=12)
    p.add_argument("--min-correct", type=int, default=None)
    p.add_argument("--bankers",     default="bankers.json")
    args = p.parse_args()

    banner()

    if not os.path.exists(args.bankers):
        print(f"{C.RE}  bankers.json not found. Run Phase 1 first.{C.R}")
        sys.exit(1)

    with open(args.bankers, encoding="utf-8") as f:
        ph1 = json.load(f)

    bankers    = ph1["bankers"]
    all_results = ph1["all_results"]
    total_games = len(all_results)
    maxt        = args.budget // TICKET_COST
    target      = args.target
    nb          = len(bankers)

    if target < 10 or target > total_games:
        target = max(10, min(target, total_games))

    need = args.min_correct if args.min_correct is not None else target - nb
    need = max(0, min(need, total_games))

    # Expected draws from the raw probabilities
    exp_draws = sum(float(r.get("p_draw") or 0.27) for r in all_results)

    print(f"  {C.CY}Budget: KES {args.budget} -> max {maxt} tickets{C.R}")
    print(f"  {C.CY}Games: {total_games} | Bankers: {nb} | Target: {target}/{total_games}{C.R}")
    print(f"  {C.CY}Expected draws from odds: ~{exp_draws:.1f}{C.R}\n")

    # Build pool from true probabilities
    print(f"  {C.GY}Building probability-proportional pool...{C.R}", end="", flush=True)
    pool = build_candidate_pool(all_results, max_candidates=1000)
    print(f" {C.GR}{len(pool)} candidates{C.R}")

    # Scenarios
    print(f"  {C.GY}Building scenarios...{C.R}", end="", flush=True)
    scen = build_scenarios(all_results, need)
    print(f" {C.GR}{len(scen)}{C.R}")

    # Greedy cover
    print(f"  {C.GY}Greedy cover...{C.R}", end="", flush=True)

    # For greedy cover, work on just the uncertain positions
    if bankers:
        bp        = {b["game"]-1: b["banker_pick"] for b in bankers}
        unc_idx   = [i for i in range(total_games) if i not in bp]
        unc_pool  = [tuple(c[i] for i in range(len(c)) if i not in bp)
                     for c in pool]
        unc_scen  = [tuple(s[i] for i in range(len(s)) if i not in bp)
                     for s in scen]
        unc_need  = need
        sel_unc   = greedy_cover(unc_pool, unc_scen, unc_need, maxt)
        sel_unc   = diversity_fill(sel_unc, unc_pool, maxt, 
                                   [all_results[i] for i in unc_idx])
        sel       = [tuple(
                        list(c) if i not in bp else []
                    ) for c in sel_unc]
        full      = assemble(sel_unc, bankers, total_games)
    else:
        sel  = greedy_cover(pool, scen, need, maxt)
        sel  = diversity_fill(sel, pool, maxt, all_results)
        full = assemble(sel, bankers, total_games)

    print(f" {C.GR}{len(full)} tickets{C.R}\n")

    ev = estimate_ev(full, all_results)

    print_summary(full, bankers, total_games, ev, target, need, exp_draws)
    print_tickets(full, bankers, total_games)
    save_tickets(full, ev, bankers, total_games, target, need)

if __name__ == "__main__":
    main()