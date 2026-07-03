#!/usr/bin/env python3
"""
================================================================
 JACKPOT PREDICTION SYSTEM — MASTER RUNNER  v4.0
 Phase 1 (Poisson model) -> Phase 2 (wheel) -> Phase 3 (filter)
================================================================
"""
import subprocess, sys, argparse, os

class C:
    R="\033[0m"; B="\033[1m"; RE="\033[91m"; GR="\033[92m"
    YE="\033[93m"; CY="\033[96m"; WH="\033[97m"; GY="\033[90m"

SCRIPT_DIR=os.path.dirname(os.path.abspath(__file__))
def script(n): return os.path.join(SCRIPT_DIR,n)

def run(cmd,label):
    print(f"\n{C.CY}{C.B}{'='*60}{C.R}\n{C.YE}{C.B}  RUNNING: {label}{C.R}\n{C.CY}{'='*60}{C.R}\n")
    r=subprocess.run([sys.executable]+cmd)
    if r.returncode!=0:
        print(f"\n{C.RE}  {label} failed.{C.R}\n"); sys.exit(r.returncode)
    print(f"\n{C.GR}  OK {label} complete{C.R}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matches",required=True)
    p.add_argument("--budget",type=int,default=500)
    p.add_argument("--target",type=int,default=12)
    p.add_argument("--threshold",type=float,default=0.55)
    p.add_argument("--api-key",default=None)
    mg=p.add_mutually_exclusive_group()
    mg.add_argument("--strict",action="store_true")
    mg.add_argument("--relax",action="store_true")
    p.add_argument("--skip-scrape",action="store_true")
    args=p.parse_args()

    if not os.path.exists(args.matches):
        print(f"{C.RE}  Matches file not found: {args.matches}{C.R}"); sys.exit(1)
    if args.target not in (12,13,14,15):
        print(f"{C.RE}  --target must be 12-15{C.R}"); sys.exit(1)
    maxt=args.budget//15
    mode="strict" if args.strict else "relax" if args.relax else "standard"

    print(f"""
{C.YE}{C.B}  ╔══════════════════════════════════════════════════════════╗
  ║      JACKPOT PREDICTION SYSTEM — FULL PIPELINE  v4.0    ║
  ║   Poisson Model -> Wheel -> Filter                      ║
  ╚══════════════════════════════════════════════════════════╝{C.R}

  {C.CY}Matches:    {args.matches}
  Budget:     KES {args.budget} -> max {maxt} tickets
  Target:     >= {args.target}/15
  Threshold:  {int(args.threshold*100)}%
  Filter:     {mode}
  Data:       {'fallback (--skip-scrape)' if args.skip_scrape else 'football-data.org API'}{C.R}
""")

    p1=[script("phase1_model.py"),"--matches",args.matches,"--threshold",str(args.threshold)]
    if args.api_key: p1+=["--api-key",args.api_key]
    if args.skip_scrape: p1.append("--no-scrape")
    run(p1,"Phase 1: Poisson Match Model")

    p2=[script("phase2_wheel.py"),"--budget",str(args.budget),"--target",str(args.target)]
    run(p2,"Phase 2: Wheel Engine")

    p3=[script("phase3_filter.py")]
    if args.strict: p3.append("--strict")
    elif args.relax: p3.append("--relax")
    run(p3,"Phase 3: Filter")

    print(f"""
{C.GR}{C.B}  ╔══ PIPELINE COMPLETE ════════════════════════════════════╗
  ║  Your optimised jackpot slips are ready.               ║
  ╚════════════════════════════════════════════════════════╝{C.R}

  {C.WH}Send each slip from final_slips.txt to 29090{C.R}

  {C.YE}If all tickets rejected, re-run with --relax{C.R}
""")

if __name__=="__main__": main()
