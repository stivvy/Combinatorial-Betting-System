#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — PHASE 2: WHEEL ENGINE  v4.0
 Budget-aware greedy covering design + diversity fill
================================================================
"""
import json, argparse, sys, os, csv, random
from itertools import product, combinations as icomb
from datetime import datetime

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

TICKET_COST=15
ALL_OUTCOMES=["1","X","2"]

def banner():
    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║   PHASE 2: WHEEL ENGINE  |  Covering Design + Fill      ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(t=""):
    if t: print(f"{C.CY}{C.B}  -- {t} {'-'*(54-len(t))}{C.R}")
    else: print(f"{C.GY}  {'-'*58}{C.R}")

def get_alternatives(g):
    a=g.get("alternatives","")
    alts=[x.strip() for x in a.split() if x.strip() in ALL_OUTCOMES] if isinstance(a,str) else []
    alts=[x for x in alts if x!=g["primary"]]
    if not alts: alts=[o for o in ALL_OUTCOMES if o!=g["primary"]]
    return alts

def build_candidate_pool(uncertain, max_candidates=600):
    n=len(uncertain); seen=set(); cand=[]
    def add(t):
        tt=tuple(t)
        if tt not in seen: seen.add(tt); cand.append(tt)
    base=tuple(g["primary"] for g in uncertain); add(base)
    for fc in range(1,min(4,n+1)):
        for idx in icomb(range(n),fc):
            ga=[get_alternatives(uncertain[i]) for i in idx]
            for combo in product(*ga):
                if len(cand)>=max_candidates: break
                t=list(base)
                for pos,i in enumerate(idx): t[i]=combo[pos]
                add(t)
            if len(cand)>=max_candidates: break
        if len(cand)>=max_candidates: break
    rng=random.Random(42); att=0
    while len(cand)<max_candidates and att<6000:
        att+=1; t=list(base)
        for i in rng.sample(range(n),rng.randint(1,min(4,n))):
            t[i]=rng.choice(get_alternatives(uncertain[i]))
        add(t)
    return cand

def build_scenarios(uncertain,need):
    n=len(uncertain); nw=max(0,n-need)
    base=tuple(g["primary"] for g in uncertain); sc=[]
    for wrong in icomb(range(n),nw):
        s=list(base)
        for w in wrong: s[w]=get_alternatives(uncertain[w])[0]
        sc.append(tuple(s))
    return sc

def score(t,s): return sum(1 for a,b in zip(t,s) if a==b)

def greedy_cover(cand,scen,target,maxt):
    unc=set(range(len(scen))); sel=[]; used=set()
    while unc and len(sel)<maxt:
        bci=-1; bc=-1; bcov=set()
        for ci,c in enumerate(cand):
            if ci in used: continue
            cov={si for si in unc if score(c,scen[si])>=target}
            if len(cov)>bc: bc=len(cov); bci=ci; bcov=cov
        if bci==-1 or bc==0: break
        sel.append(cand[bci]); used.add(bci); unc-=bcov
    return sel

def assemble(unc_tickets,bankers):
    bp={b["game"]-1:b["banker_pick"] for b in bankers}
    full=[]
    for ut in unc_tickets:
        f=[]; pos=0
        for i in range(15):
            if i in bp: f.append(bp[i])
            else: f.append(ut[pos]); pos+=1
        full.append(f)
    return full

PRIZE_TABLE={15:15_000_000,14:1_000_000,13:125_000,12:15_000}

def estimate_ev(full,allr):
    gp={}
    for r in allr:
        g=r["game"]-1
        gp[g]={"1":r.get("p_home") or .33,"X":r.get("p_draw") or .33,"2":r.get("p_away") or .33}
    ev=0.0
    for t in full:
        pc=[gp.get(g,{"1":.33,"X":.33,"2":.33}).get(p,.33) for g,p in enumerate(t)]
        dp=[0.0]*16; dp[0]=1.0
        for p in pc:
            nd=[0.0]*16
            for s in range(16):
                if dp[s]==0: continue
                nd[s]+=dp[s]*(1-p)
                if s<15: nd[s+1]+=dp[s]*p
            dp=nd
        for sc,pr in PRIZE_TABLE.items(): ev+=dp[sc]*pr
    cost=len(full)*TICKET_COST
    return {"ev":round(ev,2),"cost":cost,"roi":round((ev-cost)/cost*100,2) if cost else 0}

def print_summary(full,bankers,unc,ev,target,need):
    sep("WHEEL SUMMARY"); print()
    print(f"  {C.GR}{C.B}╔══ RESULT ═══════════════════════════════════════════════╗{C.R}")
    rows=[("Bankers locked",f"{len(bankers)} games"),
          ("Uncertain games",f"{len(unc)} games"),
          ("Tickets generated",f"{len(full)}"),
          ("Total cost",f"KES {ev['cost']}"),
          ("Target guarantee",f">= {target}/15"),
          ("Condition",f"If >= {need}/{len(unc)} uncertain right"),
          ("Expected value",f"KES {ev['ev']:,.0f}"),
          ("Expected ROI",f"{ev['roi']:+.1f}%")]
    for l,v in rows:
        col=C.GR if "ROI" in l and ev["roi"]>=0 else (C.RE if "ROI" in l else C.YE)
        print(f"  {C.GR}║ {C.R}{l:<28}{col}{v:>26}{C.R}{C.GR} ║{C.R}")
    print(f"  {C.GR}╚═══════════════════════════════════════════════════════╝{C.R}\n")

def print_tickets(full,bankers):
    sep("BETTING SLIPS"); bi={b["game"]-1 for b in bankers}
    print(f"\n  {C.GY}Key: {C.GR}Green{C.GY}=banker | {C.YE}Yellow{C.GY}=uncertain{C.R}\n")
    for i,t in enumerate(full):
        print(f"  {C.CY}Slip {i+1:>3}{C.R}: ",end="")
        for g,p in enumerate(t):
            col=C.GR+C.B if g in bi else C.YE
            print(f"{col}{p}{C.R}",end="")
            if g<14: print(f"{C.GY}-{C.R}",end="")
        print()
    print()

def save_tickets(full,ev,bankers,unc,target,need):
    with open("wheel_tickets.json","w",encoding="utf-8") as f:
        json.dump({"generated":datetime.now().isoformat(),"num_tickets":len(full),
                   "total_cost_kes":ev["cost"],"expected_value_kes":ev["ev"],
                   "expected_roi_pct":ev["roi"],"bankers_locked":len(bankers),
                   "uncertain_games":len(unc),"target_score":target,
                   "num_correct_needed":need,"tickets":full},f,indent=2)
    with open("sms_slips.txt","w",encoding="utf-8") as f:
        f.write(f"JACKPOT SLIPS\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total: {len(full)} x KES {TICKET_COST} = KES {ev['cost']}\n\n")
        f.write("BANKERS:\n")
        for b in bankers:
            c=b.get("confidence")
            cs=f"{float(c):.1f}%" if isinstance(c,(int,float)) else "?"
            f.write(f"  G{b['game']:>2}: {b['home']:<20} vs {b['away']:<20} -> {b['banker_pick']} ({cs})\n")
        f.write(f"\nSMS SLIPS (send to 29090):\n{'-'*44}\n")
        for i,t in enumerate(full): f.write(f"Slip {i+1:>3}: JP#{''.join(t)}\n")
    with open("wheel_tickets.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow([f"G{i+1}" for i in range(15)]+["SMS"])
        for t in full: w.writerow(t+["JP#"+''.join(t)])
    print(f"  {C.GR}OK wheel_tickets.json | sms_slips.txt | wheel_tickets.csv{C.R}")
    print(f"  {C.CY}  Next: python phase3_filter.py{C.R}\n")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--budget",type=int,default=500)
    p.add_argument("--target",type=int,default=12)
    p.add_argument("--min-correct",type=int,default=None)
    p.add_argument("--bankers",default="bankers.json")
    args=p.parse_args()
    banner()
    if not os.path.exists(args.bankers):
        print(f"{C.RE}  bankers.json not found{C.R}"); sys.exit(1)
    with open(args.bankers,encoding="utf-8") as f: ph1=json.load(f)
    bankers=ph1["bankers"]; unc=ph1["uncertain"]; allr=ph1["all_results"]
    maxt=args.budget//TICKET_COST; target=args.target; nb=len(bankers)
    if target<12 or target>15: print(f"{C.RE}  target 12-15{C.R}"); sys.exit(1)
    if nb>target: target=nb
    need=args.min_correct if args.min_correct is not None else target-nb
    need=max(0,min(need,len(unc)))
    print(f"  {C.CY}Budget: KES {args.budget} -> max {maxt} tickets | Bankers: {nb} | Target: {target}/15{C.R}\n")
    if not unc:
        full=[[b["banker_pick"] for b in sorted(bankers,key=lambda x:x["game"])]]
        ev=estimate_ev(full,allr); print_summary(full,bankers,unc,ev,target,0)
        print_tickets(full,bankers); save_tickets(full,ev,bankers,unc,target,0); return
    print(f"  {C.GY}Building candidates...{C.R}",end="",flush=True)
    cand=build_candidate_pool(unc,600); print(f" {C.GR}{len(cand)}{C.R}")
    print(f"  {C.GY}Building scenarios...{C.R}",end="",flush=True)
    scen=build_scenarios(unc,need); print(f" {C.GR}{len(scen)}{C.R}")
    print(f"  {C.GY}Greedy cover...{C.R}",end="",flush=True)
    sel=greedy_cover(cand,scen,need,maxt); print(f" {C.GR}{len(sel)} tickets{C.R}")
    # ── EV-WEIGHTED DIVERSITY FILL ────────────────────────────
    # Fill remaining budget with tickets ranked by a COMBINED score:
    #   50% probability weight — P(ticket's uncertain picks are correct),
    #     computed from Phase 1's per-game probabilities. This ensures we
    #     add plausible tickets, not just maximally different ones.
    #   50% diversity weight — distance from already-selected tickets,
    #     so the set still spreads across outcome combinations.
    if len(sel)<maxt:
        # Per-uncertain-game probability lookup for each outcome
        unc_probs=[]
        for g in unc:
            unc_probs.append({"1":g.get("p_home") or .33,
                              "X":g.get("p_draw") or .33,
                              "2":g.get("p_away") or .33})
        def ticket_logprob(c):
            # sum of log probabilities of each pick (higher = more plausible)
            import math
            return sum(math.log(max(unc_probs[i].get(p,.33),1e-6))
                       for i,p in enumerate(c))
        ss=set(tuple(s) for s in sel)
        rem=[c for c in cand if tuple(c) not in ss]
        if rem:
            lps=[ticket_logprob(c) for c in rem]
            lp_min,lp_max=min(lps),max(lps)
            lp_rng=(lp_max-lp_min) or 1.0
            def div(c):
                if not sel: return 0
                return sum(sum(1 for a,b in zip(c,s) if a!=b) for s in sel)/(len(sel)*len(c))
            def combined(i_c):
                i,c=i_c
                prob_norm=(lps[i]-lp_min)/lp_rng     # 0..1, higher = plausible
                return 0.5*prob_norm + 0.5*div(c)     # balance plausibility+spread
            # Constraint pre-check: build the FULL ticket (bankers + picks)
            # and skip candidates Phase 3 would reject anyway (too many
            # home wins / zero draws). This keeps Phase 2 and Phase 3
            # consistent instead of generating tickets destined for the bin.
            bp={b["game"]-1:b["banker_pick"] for b in bankers}
            def full_of(c):
                f=[]; pos=0
                for i in range(15):
                    if i in bp: f.append(bp[i])
                    else: f.append(c[pos]); pos+=1
                return f
            # Mirror Phase 3's dynamic max_consecutive (banker run + 1, min 6)
            from itertools import groupby as _gb
            _pos=sorted(bp.keys()); _mr=1; _cr=1
            for _i in range(1,len(_pos)):
                if _pos[_i]==_pos[_i-1]+1 and bp[_pos[_i]]==bp[_pos[_i-1]]:
                    _cr+=1; _mr=max(_mr,_cr)
                else: _cr=1
            _max_run=max(_mr+1,6)
            def passes_bounds(c):
                f=full_of(c)
                h=f.count("1"); d=f.count("X")
                if h>12 or d<1: return False
                run=max(len(list(g)) for _,g in _gb(f))
                return run<=_max_run
            ranked=sorted(enumerate(rem),key=combined,reverse=True)
            for _,c in ranked:
                if len(sel)>=maxt: break
                if not passes_bounds(c): continue
                if not any(all(a==b for a,b in zip(c,s)) for s in sel): sel.append(c)
            # If bounds were too tight to fill the budget, relax and top up
            if len(sel)<maxt:
                for _,c in ranked:
                    if len(sel)>=maxt: break
                    if not any(all(a==b for a,b in zip(c,s)) for s in sel): sel.append(c)
        print(f"  {C.GY}EV-weighted fill: {C.GR}{len(sel)} total{C.R}\n")
    else: print()
    full=assemble(sel,bankers); ev=estimate_ev(full,allr)
    print_summary(full,bankers,unc,ev,target,need)
    print_tickets(full,bankers); save_tickets(full,ev,bankers,unc,target,need)

if __name__=="__main__": main()
