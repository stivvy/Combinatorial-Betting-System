#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — PHASE 3: FILTER  v4.0
 Statistical pruning + market divergence (banker-adjusted)
================================================================
"""
import json, argparse, sys, os, csv
from collections import Counter
from datetime import datetime
from itertools import groupby

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

def banner():
    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║   PHASE 3: FILTER  |  Pattern Pruning + Divergence      ║
  ╚══════════════════════════════════════════════════════════╝{C.R}
""")

def sep(t=""):
    if t: print(f"{C.CY}{C.B}  -- {t} {'-'*(54-len(t))}{C.R}")
    else: print(f"{C.GY}  {'-'*58}{C.R}")

BASE={"avg_home_wins":6.2,"avg_draws":3.8,"avg_away_wins":5.0,
      "min_draws":1,"max_draws":8,"min_home_wins":3,"max_home_wins":11,
      "min_away_wins":1,"max_away_wins":9,"max_consecutive":5}

def build_patterns(bankers,mode="standard"):
    p=BASE.copy()
    if not bankers:
        if mode=="strict": p.update({"min_draws":2,"max_draws":7,"max_consecutive":4})
        elif mode=="relax": p.update({"min_draws":0,"max_draws":9,"max_consecutive":7})
        return p
    bp=[b["banker_pick"] for b in bankers]
    lh=bp.count("1"); ld=bp.count("X"); la=bp.count("2"); nu=15-len(bankers)
    p["min_home_wins"]=max(lh,3); p["max_home_wins"]=min(lh+nu,12)
    p["min_draws"]=max(ld,0); p["max_draws"]=min(ld+nu,8)
    p["min_away_wins"]=max(la,0); p["max_away_wins"]=min(la+nu,9)
    pos=sorted(b["game"]-1 for b in bankers)
    pm={b["game"]-1:b["banker_pick"] for b in bankers}
    mr=1; cr=1
    for i in range(1,len(pos)):
        if pos[i]==pos[i-1]+1 and pm[pos[i]]==pm[pos[i-1]]: cr+=1; mr=max(mr,cr)
        else: cr=1
    ma=mr+1
    if mode=="strict": p["max_consecutive"]=max(ma,5); p["min_draws"]=max(p["min_draws"],1); p["max_draws"]=min(p["max_draws"],7); p["max_home_wins"]=min(p["max_home_wins"],10)
    elif mode=="relax": p["max_consecutive"]=max(ma,8); p["max_draws"]=min(p["max_draws"]+1,9); p["max_home_wins"]=min(p["max_home_wins"]+1,13)
    else: p["max_consecutive"]=max(ma,6)
    return p

class FR:
    def __init__(s,ok,reason="",pen=0.0): s.ok=ok; s.reason=reason; s.pen=pen

def c_draw(t,p):
    d=t.count("X")
    if d<p["min_draws"]: return FR(False,f"Too few draws: {d} (min {p['min_draws']})")
    if d>p["max_draws"]: return FR(False,f"Too many draws: {d} (max {p['max_draws']})")
    return FR(True,"",max(0,abs(d-p["avg_draws"])-1.5)*0.08)

def c_home(t,p):
    h=t.count("1")
    if h<p["min_home_wins"]: return FR(False,f"Too few home: {h} (min {p['min_home_wins']})")
    if h>p["max_home_wins"]: return FR(False,f"Too many home: {h} (max {p['max_home_wins']})")
    return FR(True,"",max(0,abs(h-p["avg_home_wins"])-2.5)*0.06)

def c_away(t,p):
    a=t.count("2")
    if a<p["min_away_wins"]: return FR(False,f"Too few away: {a} (min {p['min_away_wins']})")
    if a>p["max_away_wins"]: return FR(False,f"Too many away: {a} (max {p['max_away_wins']})")
    return FR(True,"",max(0,abs(a-p["avg_away_wins"])-2.5)*0.06)

def c_run(t,p):
    mr=max(len(list(g)) for _,g in groupby(t))
    if mr>p["max_consecutive"]: return FR(False,f"Run of {mr} (max {p['max_consecutive']})")
    return FR(True,"",max(0,mr-4)*0.04)

def c_bal(t,p):
    cnt=Counter(t); h=cnt.get("1",0); d=cnt.get("X",0); a=cnt.get("2",0); tot=h+d+a
    if tot==0: return FR(True)
    pen=0.0
    if h/tot>0.87: pen+=0.15
    if d/tot>0.67: pen+=0.12
    if a/tot>0.73: pen+=0.12
    return FR(True,"",pen)

def c_alt(t):
    n=len(t)
    if n<2: return FR(True)
    alt=sum(1 for i in range(n-1) if t[i]!=t[i+1])
    return FR(True,"",max(0,alt/(n-1)-0.85)*0.25)

def score_ticket(t,p):
    checks=[c_draw(t,p),c_home(t,p),c_away(t,p),c_run(t,p),c_bal(t,p),c_alt(t)]
    for c in checks:
        if not c.ok: return {"passed":False,"reason":c.reason,"score":0.0,"draws":0,"home_wins":0,"away_wins":0}
    pen=sum(c.pen for c in checks)
    return {"passed":True,"reason":"","score":round(max(0,1-pen),4),
            "draws":t.count("X"),"home_wins":t.count("1"),"away_wins":t.count("2")}

def warn_divergence(tickets,allr):
    w=[]
    if not tickets or not allr: return w
    rm={r["game"]:r for r in allr}
    for gn,r in rm.items():
        gi=gn-1
        if gi>=len(tickets[0]): continue
        ph=r.get("p_home") or .33; pd=r.get("p_draw") or .33; pa=r.get("p_away") or .33
        pp=max(ph,pd,pa)
        pk="1" if ph==pp else ("X" if pd==pp else "2")
        ac=sum(1 for t in tickets if t[gi]==pk); ap=ac/len(tickets)*100
        if not r.get("banker") and ap>=85 and 0.45<pp<0.72:
            rk=sorted([("1",ph),("X",pd),("2",pa)],key=lambda x:x[1],reverse=True)
            w.append({"game":gn,"message":f"Game {gn} ({r.get('home','')} vs {r.get('away','')}): {round(ap)}% pick '{pk}' ({round(pp*100)}% likely). Consider 1 ticket on '{rk[1][0]}'."})
    return w

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tickets",default="wheel_tickets.json")
    p.add_argument("--bankers",default="bankers.json")
    mg=p.add_mutually_exclusive_group()
    mg.add_argument("--strict",action="store_true")
    mg.add_argument("--relax",action="store_true")
    p.add_argument("--min-score",type=float,default=0.0)
    args=p.parse_args()
    banner()
    if not os.path.exists(args.tickets):
        print(f"{C.RE}  wheel_tickets.json not found{C.R}"); sys.exit(1)
    with open(args.tickets,encoding="utf-8") as f: ph2=json.load(f)
    tickets=ph2.get("tickets",[])
    if not tickets: print(f"{C.RE}  No tickets{C.R}"); sys.exit(1)
    bankers=[]; allr=[]
    if os.path.exists(args.bankers):
        with open(args.bankers,encoding="utf-8") as f: ph1=json.load(f)
        bankers=ph1.get("bankers",[]); allr=ph1.get("all_results",[])
    mode="strict" if args.strict else "relax" if args.relax else "standard"
    patt=build_patterns(bankers,mode)
    print(f"  {C.GY}Loaded {len(tickets)} tickets | mode: {mode}{C.R}")
    print(f"  {C.GY}max_consecutive: {patt['max_consecutive']} | home range: {patt['min_home_wins']}-{patt['max_home_wins']}{C.R}\n")
    sep("APPLYING FILTERS"); print()
    scored=[]; rej=Counter()
    for t in tickets:
        r=score_ticket(t,patt)
        if r["passed"] and r["score"]>=args.min_score: scored.append((t,r))
        else: rej[r["reason"]]+=1
    scored.sort(key=lambda x:x[1]["score"],reverse=True)
    sep("FILTER RESULTS"); print()
    print(f"  Original: {C.WH}{len(tickets)}{C.R} | Rejected: {C.RE}{len(tickets)-len(scored)}{C.R} | Surviving: {C.GR}{len(scored)}{C.R}\n")
    if rej:
        print(f"  {C.RE}Rejection reasons:{C.R}")
        for r,c in rej.most_common(): print(f"    {C.GY}{c}x{C.R} {r}")
        print()
    surv=[t for t,_ in scored]
    warns=warn_divergence(surv,allr)
    sep("SURVIVING TICKETS (top 15 by score)"); print()
    print(f"  {C.GY}{'#':<4}{'Score':>7}  {'Ticket':<20}{'H':>4}{'X':>4}{'A':>4}{C.R}")
    for i,(t,sc) in enumerate(scored[:15]):
        col=C.GR if sc["score"]>0.8 else (C.YE if sc["score"]>0.5 else C.RE)
        print(f"  {i+1:<4}{col}{sc['score']:>7.3f}{C.R}  {''.join(t):<20}{sc['home_wins']:>4}{sc['draws']:>4}{sc['away_wins']:>4}")
    print()
    if warns:
        sep("MARKET DIVERGENCE"); print()
        for w in warns: print(f"  {C.YE}!  {w['message']}{C.R}")
        print()
    # Save
    with open("filtered_tickets.json","w",encoding="utf-8") as f:
        json.dump({"generated":datetime.now().isoformat(),
                   "original_tickets":ph2.get("num_tickets",0),
                   "filtered_tickets":len(scored),"total_cost_kes":len(scored)*15,
                   "market_warnings":len(warns),"warnings":warns,
                   "tickets":surv,
                   "scored_tickets":[{"ticket":t,"score":sc["score"],"home_wins":sc["home_wins"],"draws":sc["draws"],"away_wins":sc["away_wins"]} for t,sc in scored]},f,indent=2)
    with open("final_slips.txt","w",encoding="utf-8") as f:
        f.write(f"JACKPOT FINAL SLIPS\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Tickets: {len(scored)} x KES 15 = KES {len(scored)*15}\n\n")
        if warns:
            f.write("DIVERGENCE NOTES:\n")
            for w in warns: f.write(f"  ! {w['message']}\n")
            f.write("\n")
        f.write(f"SMS SLIPS (send to 29090):\n{'-'*44}\n")
        for i,(t,sc) in enumerate(scored): f.write(f"Slip {i+1:>3}: JP#{''.join(t)}  [{sc['score']:.3f} {sc['home_wins']}H/{sc['draws']}X/{sc['away_wins']}A]\n")
    with open("final_slips.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow([f"G{i+1}" for i in range(15)]+["Score","H","X","A","SMS"])
        for t,sc in scored: w.writerow(t+[sc["score"],sc["home_wins"],sc["draws"],sc["away_wins"],"JP#"+''.join(t)])
    print(f"  {C.GR}OK filtered_tickets.json | final_slips.txt | final_slips.csv{C.R}\n")
    sep("COMPLETE"); print()
    print(f"  {C.GR}{C.B}Total slips: {len(scored)} | Cost: KES {len(scored)*15}{C.R}")
    print(f"  {C.CY}Send each slip from final_slips.txt to 29090{C.R}")
    if not scored and mode=="standard":
        print(f"\n  {C.YE}  All rejected. Try: python phase3_filter.py --relax{C.R}")
    print()

if __name__=="__main__": main()
