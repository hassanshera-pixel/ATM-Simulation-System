"""
ATM Simulation System — GUI Registration Edition
=================================================
Full browser-based GUI for both registration and ATM usage.
Black & navy blue creative interface. No external libraries needed.

Run:
    python atm_simulation.py

Then open: http://localhost:8080
"""

import json
import http.server
import webbrowser
import threading
from datetime import datetime
import os


# ══════════════════════════════════════════════════════════════
#  DOMAIN LAYER
# ══════════════════════════════════════════════════════════════

class BankAccount:
    MAX_WITHDRAW = 10_000
    MAX_DEPOSIT  = 50_000

    def __init__(self, account_number, holder, pin, balance=0.0):
        self._account_number = account_number
        self._holder         = holder
        self._pin            = pin
        self._balance        = float(balance)

    @property
    def account_number(self): return self._account_number
    @property
    def holder(self):         return self._holder
    @property
    def balance(self):        return self._balance

    def verify_pin(self, pin):
        return self._pin == pin

    def deposit(self, amount):
        if amount <= 0:
            return {"ok": False, "msg": "Amount must be positive."}
        if amount > self.MAX_DEPOSIT:
            return {"ok": False, "msg": f"Max single deposit is ${self.MAX_DEPOSIT:,.2f}."}
        self._balance += amount
        return {"ok": True, "msg": f"${amount:,.2f} deposited.", "balance": self._balance}

    def withdraw(self, amount):
        if amount <= 0:
            return {"ok": False, "msg": "Amount must be positive."}
        if amount > self.MAX_WITHDRAW:
            return {"ok": False, "msg": f"Max single withdrawal is ${self.MAX_WITHDRAW:,.2f}."}
        if amount > self._balance:
            return {"ok": False, "msg": "Insufficient funds."}
        self._balance -= amount
        return {"ok": True, "msg": f"${amount:,.2f} withdrawn.", "balance": self._balance}


class Transaction:
    def __init__(self, kind, amount, balance_after):
        self.kind          = kind
        self.amount        = amount
        self.balance_after = balance_after
        self.timestamp     = datetime.now().strftime("%d %b %Y  %H:%M:%S")

    def to_dict(self):
        return {"kind": self.kind, "amount": self.amount,
                "balance": self.balance_after, "time": self.timestamp}


class ATMController:
    MAX_PIN_ATTEMPTS = 3

    def __init__(self):
        self._accounts      = {}
        self._session       = None
        self._pin_attempts  = 0
        self._locked        = False
        self._history       = []

    def register(self, account_number, holder, pin, balance=0.0):
        if not account_number or not holder or not pin:
            return {"ok": False, "msg": "All fields are required."}
        if account_number in self._accounts:
            return {"ok": False, "msg": "Account number already exists."}
        if not account_number.isdigit() or len(account_number) < 4:
            return {"ok": False, "msg": "Account number must be at least 4 digits."}
        if not pin.isdigit() or not (4 <= len(pin) <= 6):
            return {"ok": False, "msg": "PIN must be 4–6 digits."}
        if balance < 0:
            return {"ok": False, "msg": "Opening balance cannot be negative."}
        self._accounts[account_number] = BankAccount(account_number, holder, pin, balance)
        return {"ok": True, "msg": "Account created!", "account": account_number, "holder": holder}

    def login(self, account_number, pin):
        if self._locked:
            return {"ok": False, "msg": "Card blocked. Contact your bank."}
        acc = self._accounts.get(account_number)
        if not acc:
            return {"ok": False, "msg": "Account not found."}
        if not acc.verify_pin(pin):
            self._pin_attempts += 1
            rem = self.MAX_PIN_ATTEMPTS - self._pin_attempts
            if rem <= 0:
                self._locked = True
                return {"ok": False, "msg": "Too many wrong PINs. Card blocked."}
            return {"ok": False, "msg": f"Wrong PIN. {rem} attempt(s) left."}
        self._session     = acc
        self._pin_attempts = 0
        self._history.clear()
        return {"ok": True, "holder": acc.holder,
                "account": acc.account_number, "balance": acc.balance}

    def logout(self):
        self._session = None
        self._history.clear()

    def _sess(self):
        if not self._session:
            return {"ok": False, "msg": "No active session."}
        return None

    def check_balance(self):
        e = self._sess()
        if e: return e
        acc = self._session
        self._history.append(Transaction("balance", 0, acc.balance))
        return {"ok": True, "balance": acc.balance,
                "holder": acc.holder, "account": acc.account_number}

    def deposit(self, amount):
        e = self._sess()
        if e: return e
        r = self._session.deposit(amount)
        if r["ok"]: self._history.append(Transaction("deposit", amount, r["balance"]))
        return r

    def withdraw(self, amount):
        e = self._sess()
        if e: return e
        r = self._session.withdraw(amount)
        if r["ok"]: self._history.append(Transaction("withdraw", amount, r["balance"]))
        return r

    def get_history(self):
        return [t.to_dict() for t in self._history]

    def account_list(self):
        return [{"number": a.account_number, "holder": a.holder}
                for a in self._accounts.values()]


# ══════════════════════════════════════════════════════════════
#  HTTP LAYER
# ══════════════════════════════════════════════════════════════

atm = ATMController()

class ATMHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        self._html(HTML) if self.path == "/" else self._json({"ok": False}, 404)

    def do_POST(self):
        d = self._body()
        p = self.path
        if   p == "/api/register": res = atm.register(d.get("account",""), d.get("holder",""), d.get("pin",""), float(d.get("balance",0) or 0))
        elif p == "/api/login":    res = atm.login(d.get("account",""), d.get("pin",""))
        elif p == "/api/balance":  res = atm.check_balance()
        elif p == "/api/deposit":
            try: amt = float(d.get("amount",0))
            except: amt = 0
            res = atm.deposit(amt)
        elif p == "/api/withdraw":
            try: amt = float(d.get("amount",0))
            except: amt = 0
            res = atm.withdraw(amt)
        elif p == "/api/history":  res = {"ok": True, "history": atm.get_history()}
        elif p == "/api/logout":   atm.logout(); res = {"ok": True}
        elif p == "/api/accounts": res = {"ok": True, "accounts": atm.account_list()}
        else: res = {"ok": False, "msg": "Not found"}
        self._json(res)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST,GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ══════════════════════════════════════════════════════════════
#  FULL HTML FRONTEND
# ══════════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Pacer Bank Limited — ATM</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --black:#040608;
  --navy-deep:#060C1A;
  --navy:#0A1628;
  --navy-mid:#0F2040;
  --navy-light:#162D5A;
  --navy-border:#1E3A6E;
  --navy-glow:#1A4A8A;
  --blue:#1E6FD9;
  --blue-bright:#2E8BF5;
  --blue-soft:#4DA3FF;
  --cyan:#00D4FF;
  --cyan-dim:#00A8CC;
  --white:#F0F4FF;
  --white-dim:#A8B8D8;
  --white-faint:#4A5A78;
  --success:#00E5A0;
  --danger:#FF3D5A;
  --warning:#FFB830;
  --mono:'Space Mono',monospace;
  --sans:'Space Grotesk',sans-serif;
}
html,body{height:100%;background:var(--black)}
body{
  font-family:var(--sans);
  color:var(--white);
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:20px;
  background:
    radial-gradient(ellipse 80% 60% at 15% 10%, rgba(14,40,90,0.9) 0%, transparent 55%),
    radial-gradient(ellipse 60% 80% at 85% 90%, rgba(8,25,60,0.8) 0%, transparent 55%),
    linear-gradient(160deg, #040608 0%, #060C1A 40%, #040608 100%);
}

/* ── grid bg lines ───────────────────────────────── */
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:
    linear-gradient(rgba(30,111,217,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30,111,217,0.04) 1px, transparent 1px);
  background-size:48px 48px;
}

/* ══ SHELL ════════════════════════════════════════ */
.shell{
  position:relative;z-index:1;
  width:100%;max-width:480px;
  background:linear-gradient(160deg, var(--navy-mid) 0%, var(--navy) 60%, var(--navy-deep) 100%);
  border:1px solid var(--navy-border);
  border-radius:28px;
  overflow:hidden;
  box-shadow:
    0 0 0 1px rgba(30,111,217,0.15),
    0 40px 80px rgba(0,0,0,0.8),
    0 0 60px rgba(14,40,90,0.4) inset;
}

/* ── top accent bar ──────────────────────────────── */
.accent-bar{
  height:3px;
  background:linear-gradient(90deg, transparent 0%, var(--blue) 30%, var(--cyan) 65%, transparent 100%);
}

/* ── header ──────────────────────────────────────── */
.hdr{
  padding:22px 28px 18px;
  display:flex;align-items:center;gap:14px;
  border-bottom:1px solid rgba(30,111,217,0.15);
  background:rgba(6,12,26,0.5);
}
.logo{  
  width:42px;height:42px;border-radius:12px;flex-shrink:0;
  background:linear-gradient(135deg, var(--blue) 0%, var(--cyan-dim) 100%);
  display:flex;align-items:center;justify-content:center;
  font-family:var(--mono);font-size:17px;font-weight:700;color:#fff;
  box-shadow:0 4px 16px rgba(30,111,217,0.4);
}
.hdr-txt .name{font-size:15px;font-weight:600;letter-spacing:.03em;color:var(--white)}
.hdr-txt .sub{font-size:10px;color:var(--white-faint);letter-spacing:.14em;text-transform:uppercase;margin-top:2px;font-family:var(--mono)}
.pulse{
  margin-left:auto;width:9px;height:9px;border-radius:50%;
  background:var(--success);flex-shrink:0;
  box-shadow:0 0 8px var(--success);
  animation:beat 2.4s infinite;
}
@keyframes beat{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}

/* ── screen ──────────────────────────────────────── */
.screen{padding:28px;min-height:420px;display:flex;flex-direction:column}

/* ── pages ───────────────────────────────────────── */
.pg{display:none;flex-direction:column;gap:18px;animation:rise .28s ease}
.pg.on{display:flex}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── section header ──────────────────────────────── */
.sec-tag{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--white-faint);font-family:var(--mono)}
.sec-h{font-size:23px;font-weight:700;color:var(--white);line-height:1.2;margin-top:2px}
.sec-p{font-size:13px;color:var(--white-dim);line-height:1.65}

/* ── field ───────────────────────────────────────── */
.field{display:flex;flex-direction:column;gap:7px}
.field .lbl{
  font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--white-faint);font-family:var(--mono);
}
.field input{
  background:rgba(6,12,26,0.7);
  border:1px solid var(--navy-border);
  border-radius:12px;
  padding:13px 16px;
  color:var(--white);
  font-family:var(--mono);font-size:16px;
  outline:none;
  transition:border-color .2s,box-shadow .2s;
  width:100%;
}
.field input:focus{
  border-color:var(--blue-bright);
  box-shadow:0 0 0 3px rgba(46,139,245,0.15), 0 0 20px rgba(46,139,245,0.08) inset;
}
.field input::placeholder{color:var(--white-faint);font-size:14px}

/* ── strength bar ────────────────────────────────── */
.strength-wrap{display:flex;gap:5px;margin-top:2px}
.strength-seg{
  height:3px;flex:1;border-radius:2px;
  background:var(--navy-border);transition:background .3s;
}

/* ── buttons ─────────────────────────────────────── */
.btn{
  width:100%;padding:14px;border-radius:13px;
  font-family:var(--sans);font-size:14px;font-weight:600;
  cursor:pointer;border:none;transition:all .18s;letter-spacing:.03em;
}
.btn-primary{
  background:linear-gradient(135deg, var(--blue) 0%, var(--blue-bright) 100%);
  color:#fff;
  box-shadow:0 4px 20px rgba(30,111,217,0.4);
}
.btn-primary:hover{filter:brightness(1.12);transform:translateY(-1px);box-shadow:0 8px 28px rgba(30,111,217,0.5)}
.btn-primary:active{transform:translateY(0)}
.btn-ghost{
  background:rgba(30,111,217,0.08);
  color:var(--white-dim);
  border:1px solid var(--navy-border);
}
.btn-ghost:hover{background:rgba(30,111,217,0.15);border-color:var(--blue);color:var(--white)}
.btn-red{background:rgba(255,61,90,0.12);color:var(--danger);border:1px solid rgba(255,61,90,0.25)}
.btn-red:hover{background:rgba(255,61,90,0.22)}
.btn-cyan{
  background:linear-gradient(135deg, var(--cyan-dim) 0%, var(--cyan) 100%);
  color:var(--navy-deep);font-weight:700;
}
.btn-cyan:hover{filter:brightness(1.1);transform:translateY(-1px)}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.g4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px}
.qbtn{
  padding:10px 6px;border-radius:10px;font-size:12px;font-weight:600;
  background:rgba(30,111,217,0.1);border:1px solid var(--navy-border);
  color:var(--blue-soft);cursor:pointer;transition:all .15s;font-family:var(--mono);
}
.qbtn:hover{background:rgba(30,111,217,0.2);border-color:var(--blue);color:var(--white)}

/* ── toast ───────────────────────────────────────── */
.toast{
  padding:12px 16px;border-radius:11px;
  font-size:13px;font-weight:500;
  display:none;
}
.toast.on{display:block;animation:rise .2s ease}
.toast.ok{background:rgba(0,229,160,0.1);border:1px solid rgba(0,229,160,0.25);color:var(--success)}
.toast.err{background:rgba(255,61,90,0.1);border:1px solid rgba(255,61,90,0.25);color:var(--danger)}
.toast.info{background:rgba(30,111,217,0.1);border:1px solid rgba(30,111,217,0.3);color:var(--blue-soft)}

/* ── balance card ────────────────────────────────── */
.bal-card{
  background:linear-gradient(135deg, rgba(14,32,64,0.9) 0%, rgba(22,45,90,0.7) 100%);
  border:1px solid var(--navy-border);
  border-radius:18px;padding:24px;
  position:relative;overflow:hidden;
}
.bal-card::after{
  content:'';position:absolute;right:-20px;top:-20px;
  width:100px;height:100px;border-radius:50%;
  background:radial-gradient(circle, rgba(0,212,255,0.08) 0%, transparent 70%);
}
.bal-lbl{font-size:11px;color:var(--white-faint);letter-spacing:.12em;text-transform:uppercase;font-family:var(--mono)}
.bal-amt{
  font-size:40px;font-weight:700;font-family:var(--mono);
  color:var(--cyan);margin:10px 0 4px;letter-spacing:-.02em;
  text-shadow:0 0 20px rgba(0,212,255,0.25);
}
.bal-name{font-size:13px;color:var(--white-dim)}
.bal-acct{
  font-size:11px;font-family:var(--mono);
  background:rgba(30,111,217,0.15);border:1px solid rgba(30,111,217,0.2);
  padding:3px 10px;border-radius:6px;display:inline-block;
  color:var(--blue-soft);margin-top:8px;
}

/* ── history ─────────────────────────────────────── */
.hist{display:flex;flex-direction:column;gap:8px;max-height:270px;overflow-y:auto;padding-right:2px}
.hist::-webkit-scrollbar{width:3px}
.hist::-webkit-scrollbar-thumb{background:var(--navy-border);border-radius:2px}
.tx{
  display:flex;align-items:center;gap:12px;
  background:rgba(6,12,26,0.6);
  border:1px solid var(--navy-border);
  border-radius:12px;padding:12px 14px;
  transition:border-color .2s;
}
.tx:hover{border-color:var(--blue)}
.tx-ic{
  width:36px;height:36px;border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-size:15px;flex-shrink:0;font-family:var(--mono);font-weight:700;
}
.tx-ic.deposit{background:rgba(0,229,160,0.12);color:var(--success)}
.tx-ic.withdraw{background:rgba(255,61,90,0.12);color:var(--danger)}
.tx-ic.balance{background:rgba(0,212,255,0.1);color:var(--cyan)}
.tx-info{flex:1}
.tx-k{font-size:13px;font-weight:600;text-transform:capitalize;color:var(--white)}
.tx-t{font-size:11px;color:var(--white-faint);font-family:var(--mono);margin-top:2px}
.tx-v{font-family:var(--mono);font-size:13px;font-weight:700;text-align:right}
.tx-v.deposit{color:var(--success)}
.tx-v.withdraw{color:var(--danger)}
.tx-v.balance{color:var(--cyan)}
.tx-b{font-size:11px;color:var(--white-faint);font-family:var(--mono);text-align:right;margin-top:2px}

/* ── divider ─────────────────────────────────────── */
.div{height:1px;background:rgba(30,111,217,0.12);margin:2px 0}

/* ── footer ──────────────────────────────────────── */
.ftr{
  padding:14px 28px;
  display:flex;align-items:center;gap:10px;
  border-top:1px solid rgba(30,111,217,0.12);
  background:rgba(4,6,8,0.4);
}
.ftr-dot{width:6px;height:6px;border-radius:50%;background:var(--blue);box-shadow:0 0 6px var(--blue)}
.ftr-txt{font-size:11px;color:var(--white-faint);font-family:var(--mono);letter-spacing:.08em}

/* ── registered accounts list ────────────────────── */
.acc-list{display:flex;flex-direction:column;gap:8px;max-height:200px;overflow-y:auto}
.acc-row{
  display:flex;align-items:center;gap:12px;
  background:rgba(6,12,26,0.6);border:1px solid var(--navy-border);
  border-radius:11px;padding:11px 14px;
}
.acc-av{
  width:34px;height:34px;border-radius:9px;flex-shrink:0;
  background:linear-gradient(135deg,var(--blue),var(--cyan-dim));
  display:flex;align-items:center;justify-content:center;
  font-size:12px;font-weight:700;color:#fff;
}
.acc-n{font-size:13px;font-weight:600;color:var(--white)}
.acc-no{font-size:11px;color:var(--white-faint);font-family:var(--mono);margin-top:2px}

/* ── pin dots ────────────────────────────────────── */
.pin-row{display:flex;gap:10px;justify-content:center;padding:8px 0}
.pin-dot{
  width:14px;height:14px;border-radius:50%;
  border:2px solid var(--navy-border);
  background:transparent;transition:all .2s;
}
.pin-dot.filled{background:var(--blue-bright);border-color:var(--blue-bright);box-shadow:0 0 8px rgba(46,139,245,0.5)}

/* ── eye toggle button ───────────────────────────── */
.eye-btn{
  background:none;border:none;cursor:pointer;
  color:var(--white-faint);padding:2px 4px;
  border-radius:6px;display:flex;align-items:center;
  transition:color .2s, background .2s;
}
.eye-btn:hover{color:var(--blue-soft);background:rgba(30,111,217,0.12)}
.eye-btn.active{color:var(--cyan)}

/* ── step indicator ──────────────────────────────── */
.steps{display:flex;gap:8px;align-items:center;margin-bottom:4px}
.step-dot{width:8px;height:8px;border-radius:50%;background:var(--navy-border);transition:all .3s}
.step-dot.done{background:var(--blue);box-shadow:0 0 6px var(--blue)}
.step-dot.active{background:var(--cyan);box-shadow:0 0 8px var(--cyan);transform:scale(1.2)}
</style>
</head>
<body>
<div class="shell">
  <div class="accent-bar"></div>

  <!-- HEADER -->
  <div class="hdr">
    <div class="logo">PB</div>
    <div class="hdr-txt">
      <div class="name">Pacer Bank Limited</div>
      <div class="sub">ATM Terminal  ·  v3.0</div>
    </div>
    <div class="pulse" title="Online"></div>
  </div>

  <!-- SCREEN -->
  <div class="screen">

    <!-- ① WELCOME / CHOICE -->
    <div class="pg on" id="pg-welcome">
      <div>
        <div class="sec-tag">Welcome</div>
        <div class="sec-h">What would you<br>like to do?</div>
      </div>
      <button class="btn btn-primary" onclick="go('pg-register')">
        + Create New Account
      </button>
      <button class="btn btn-ghost" onclick="loadAccounts(); go('pg-login')">
        Login to Existing Account
      </button>
      <div style="margin-top:8px;text-align:center">
        <span style="font-size:12px;color:var(--white-faint);font-family:var(--mono)">
          Secured by 256-bit encryption
        </span>
      </div>
    </div>

    <!-- ② REGISTER -->
    <div class="pg" id="pg-register">
      <div>
        <div class="steps">
          <div class="step-dot active" id="sd1"></div>
          <div style="flex:1;height:1px;background:var(--navy-border)"></div>
          <div class="step-dot" id="sd2"></div>
          <div style="flex:1;height:1px;background:var(--navy-border)"></div>
          <div class="step-dot" id="sd3"></div>
        </div>
        <div class="sec-tag" style="margin-top:10px">New Account</div>
        <div class="sec-h">Create your account</div>
      </div>

      <div class="field">
        <div class="lbl">Full Name</div>
        <input id="r-name" type="text" placeholder="e.g. Sarah Connor" autocomplete="off"
               oninput="stepDots()"/>
      </div>
      <div class="field">
        <div class="lbl">Account Number (min 4 digits)</div>
        <input id="r-acc" type="text" maxlength="12" placeholder="e.g. 100101"
               autocomplete="off" oninput="stepDots()"/>
      </div>
      <div class="field">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div class="lbl">Set PIN (4–6 digits)</div>
          <button type="button" class="eye-btn" onclick="togglePin('r-pin','eye1')" id="eye1" aria-label="Show PIN">
            <svg id="eye1-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <input id="r-pin" type="password" maxlength="6" placeholder="····"
               autocomplete="off" oninput="pinStrength(); stepDots()"/>
        <div class="strength-wrap" id="str-segs">
          <div class="strength-seg" id="s0"></div>
          <div class="strength-seg" id="s1"></div>
          <div class="strength-seg" id="s2"></div>
          <div class="strength-seg" id="s3"></div>
        </div>
      </div>
      <div class="field">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div class="lbl">Confirm PIN</div>
          <button type="button" class="eye-btn" onclick="togglePin('r-pin2','eye2')" id="eye2" aria-label="Show confirm PIN">
            <svg id="eye2-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <input id="r-pin2" type="password" maxlength="6" placeholder="····"
               autocomplete="off"/>
      </div>
      <div class="field">
        <div class="lbl">Opening Balance (USD) — optional</div>
        <input id="r-bal" type="number" min="0" step="any" placeholder="0.00"/>
      </div>

      <div id="t-reg" class="toast"></div>
      <button class="btn btn-primary" onclick="doRegister()">Create Account →</button>
      <button class="btn btn-ghost" onclick="go('pg-welcome')">← Back</button>
    </div>

    <!-- ③ REGISTER SUCCESS -->
    <div class="pg" id="pg-reg-ok">
      <div style="text-align:center;padding:10px 0">
        <div style="font-size:48px;margin-bottom:12px">✦</div>
        <div class="sec-tag" style="justify-content:center;display:flex">Success</div>
        <div class="sec-h" style="text-align:center;font-size:20px;margin-top:4px">Account Created!</div>
      </div>
      <div class="bal-card" id="reg-summary">
        <div class="bal-lbl">Account Holder</div>
        <div class="bal-amt" id="rs-name" style="font-size:22px;color:var(--white)">—</div>
        <div class="bal-acct" id="rs-acc">—</div>
        <div style="margin-top:14px;display:flex;justify-content:space-between;align-items:center">
          <span class="bal-lbl">Opening Balance</span>
          <span style="font-family:var(--mono);color:var(--cyan);font-weight:700" id="rs-bal">$0.00</span>
        </div>
      </div>
      <button class="btn btn-primary" onclick="go('pg-welcome')">Back to Home</button>
      <button class="btn btn-ghost" onclick="go('pg-register'); clearReg()">Register Another</button>
    </div>

    <!-- ④ LOGIN -->
    <div class="pg" id="pg-login">
      <div>
        <div class="sec-tag">Authentication</div>
        <div class="sec-h">Login to your<br>account</div>
      </div>

      <!-- registered accounts preview -->
      <div id="acc-preview" style="display:none">
        <div class="lbl" style="font-size:10px;letter-spacing:.1em;color:var(--white-faint);font-family:var(--mono);margin-bottom:8px">REGISTERED ACCOUNTS</div>
        <div class="acc-list" id="acc-list-el"></div>
      </div>

      <div class="field">
        <div class="lbl">Account Number</div>
        <input id="l-acc" type="text" maxlength="12" placeholder="Your account number" autocomplete="off"/>
      </div>
      <div class="field">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div class="lbl">PIN</div>
          <button type="button" class="eye-btn" onclick="togglePin('l-pin','eye3')" id="eye3" aria-label="Show PIN">
            <svg id="eye3-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <input id="l-pin" type="password" maxlength="6" placeholder="····"
               autocomplete="off" oninput="syncDots(this.value)"/>
        <div class="pin-row" id="pin-dots">
          <div class="pin-dot" id="pd0"></div>
          <div class="pin-dot" id="pd1"></div>
          <div class="pin-dot" id="pd2"></div>
          <div class="pin-dot" id="pd3"></div>
          <div class="pin-dot" id="pd4"></div>
          <div class="pin-dot" id="pd5"></div>
        </div>
      </div>

      <div id="t-login" class="toast"></div>
      <button class="btn btn-cyan" onclick="doLogin()">Verify & Enter →</button>
      <button class="btn btn-ghost" onclick="go('pg-welcome')">← Back</button>
    </div>

    <!-- ⑤ DASHBOARD -->
    <div class="pg" id="pg-dash">
      <div>
        <div class="sec-tag">Dashboard</div>
        <div class="sec-h" id="dash-hi">Hello</div>
      </div>
      <div class="bal-card">
        <div class="bal-lbl">Available Balance</div>
        <div class="bal-amt" id="d-bal">$0.00</div>
        <div class="bal-name" id="d-name">—</div>
        <div class="bal-acct" id="d-acc">—</div>
      </div>
      <div class="g2">
        <button class="btn btn-ghost" onclick="go('pg-deposit')">↑ Deposit</button>
        <button class="btn btn-ghost" onclick="go('pg-withdraw')">↓ Withdraw</button>
      </div>
      <button class="btn btn-ghost" onclick="doBalance()">◈ Check Balance</button>
      <button class="btn btn-ghost" onclick="doHistory()">≡ Transaction History</button>
      <div class="div"></div>
      <button class="btn btn-red" onclick="doLogout()">⏻ Logout</button>
    </div>

    <!-- ⑥ DEPOSIT -->
    <div class="pg" id="pg-deposit">
      <div>
        <div class="sec-tag">Deposit Funds</div>
        <div class="sec-h">How much to deposit?</div>
      </div>
      <div class="field">
        <div class="lbl">Amount (USD)</div>
        <input id="inp-dep" type="number" min="1" step="any" placeholder="0.00"/>
      </div>
      <div class="g4">
        <button class="qbtn" onclick="qa('inp-dep',100)">$100</button>
        <button class="qbtn" onclick="qa('inp-dep',500)">$500</button>
        <button class="qbtn" onclick="qa('inp-dep',1000)">$1K</button>
        <button class="qbtn" onclick="qa('inp-dep',5000)">$5K</button>
      </div>
      <div id="t-dep" class="toast"></div>
      <button class="btn btn-primary" onclick="doDeposit()">Confirm Deposit →</button>
      <button class="btn btn-ghost" onclick="go('pg-dash')">← Back</button>
    </div>

    <!-- ⑦ WITHDRAW -->
    <div class="pg" id="pg-withdraw">
      <div>
        <div class="sec-tag">Withdraw Funds</div>
        <div class="sec-h">How much to withdraw?</div>
      </div>
      <div class="field">
        <div class="lbl">Amount (USD)</div>
        <input id="inp-wd" type="number" min="1" step="any" placeholder="0.00"/>
      </div>
      <div class="g4">
        <button class="qbtn" onclick="qa('inp-wd',20)">$20</button>
        <button class="qbtn" onclick="qa('inp-wd',50)">$50</button>
        <button class="qbtn" onclick="qa('inp-wd',100)">$100</button>
        <button class="qbtn" onclick="qa('inp-wd',200)">$200</button>
      </div>
      <div id="t-wd" class="toast"></div>
      <button class="btn btn-primary" onclick="doWithdraw()">Confirm Withdrawal →</button>
      <button class="btn btn-ghost" onclick="go('pg-dash')">← Back</button>
    </div>

    <!-- ⑧ BALANCE -->
    <div class="pg" id="pg-bal">
      <div>
        <div class="sec-tag">Balance Enquiry</div>
        <div class="sec-h">Your balance</div>
      </div>
      <div class="bal-card">
        <div class="bal-lbl">Current Balance</div>
        <div class="bal-amt" id="b-amt">$0.00</div>
        <div class="bal-name" id="b-name">—</div>
        <div class="bal-acct" id="b-acc">—</div>
        <div style="margin-top:14px">
          <span style="font-size:11px;color:var(--white-faint);font-family:var(--mono)" id="b-time"></span>
        </div>
      </div>
      <button class="btn btn-ghost" onclick="go('pg-dash')">← Back to Menu</button>
    </div>

    <!-- ⑨ HISTORY -->
    <div class="pg" id="pg-hist">
      <div>
        <div class="sec-tag">Session History</div>
        <div class="sec-h">Transactions</div>
      </div>
      <div class="hist" id="hist-list">
        <div style="color:var(--white-faint);font-size:13px;text-align:center;padding:24px 0;font-family:var(--mono)">
          No transactions yet
        </div>
      </div>
      <button class="btn btn-ghost" onclick="go('pg-dash')">← Back</button>
    </div>

  </div><!-- /screen -->

  <!-- FOOTER -->
  <div class="ftr">
    <div class="ftr-dot"></div>
    <div class="ftr-txt" id="ftr">SECURE CONNECTION ESTABLISHED</div>
  </div>
</div>

<script>
const $=id=>document.getElementById(id);
const fmt=n=>'$'+parseFloat(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});

function go(id){
  document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));
  $(id).classList.add('on');
}

function toast(id,msg,type='ok'){
  const el=$(id);
  el.textContent=msg;
  el.className='toast on '+type;
  clearTimeout(el._t);
  el._t=setTimeout(()=>el.classList.remove('on'),4500);
}

async function api(ep,body={}){
  const r=await fetch(ep,{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});
  return r.json();
}

function qa(id,v){$(id).value=v}

/* ── show / hide PIN toggle ─────────────────── */
const eyeOff=`<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
const eyeOn=`<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;

function togglePin(inputId, btnId){
  const inp=$(inputId);
  const btn=$(btnId);
  const isHidden = inp.type==='password';
  inp.type = isHidden ? 'text' : 'password';
  btn.innerHTML = isHidden ? eyeOff : eyeOn;
  btn.classList.toggle('active', isHidden);
  btn.setAttribute('aria-label', isHidden ? 'Hide PIN' : 'Show PIN');
}

/* ── PIN strength bar ───────────────────────── */
function pinStrength(){
  const v=$('r-pin').value;
  const colors=['#FF3D5A','#FFB830','#2E8BF5','#00E5A0'];
  for(let i=0;i<4;i++){
    $('s'+i).style.background = i<v.length ? colors[Math.min(i,colors.length-1)] : 'var(--navy-border)';
  }
}

/* ── step dots ──────────────────────────────── */
function stepDots(){
  const n=$('r-name').value.trim().length>1;
  const a=$('r-acc').value.trim().length>=4;
  const p=$('r-pin').value.trim().length>=4;
  $('sd1').className='step-dot '+(n?'done':'active');
  $('sd2').className='step-dot '+(a?'done': n?'active':'');
  $('sd3').className='step-dot '+(p?'done': a?'active':'');
}

/* ── PIN dots (login) ───────────────────────── */
function syncDots(v){
  for(let i=0;i<6;i++)
    $('pd'+i).className='pin-dot'+(i<v.length?' filled':'');
}

/* ── REGISTER ───────────────────────────────── */
function clearReg(){
  ['r-name','r-acc','r-pin','r-pin2','r-bal'].forEach(id=>$(id).value='');
  pinStrength(); stepDots();
}

async function doRegister(){
  const holder=$('r-name').value.trim();
  const account=$('r-acc').value.trim();
  const pin=$('r-pin').value.trim();
  const pin2=$('r-pin2').value.trim();
  const balance=parseFloat($('r-bal').value)||0;

  if(!holder||holder.length<2){toast('t-reg','Please enter your full name.','err');return;}
  if(pin!==pin2){toast('t-reg','PINs do not match.','err');return;}

  const res=await api('/api/register',{account,holder,pin,balance});
  if(res.ok){
    $('rs-name').textContent=holder;
    $('rs-acc').textContent='Acc •••• '+account.slice(-4);
    $('rs-bal').textContent=fmt(balance);
    clearReg();
    go('pg-reg-ok');
  }else{
    toast('t-reg',res.msg,'err');
  }
}

/* ── LOAD ACCOUNTS ──────────────────────────── */
async function loadAccounts(){
  const res=await api('/api/accounts');
  const el=$('acc-list-el');
  const wrap=$('acc-preview');
  if(res.ok && res.accounts.length>0){
    el.innerHTML=res.accounts.map(a=>`
      <div class="acc-row" onclick="$('l-acc').value='${a.number}';$('l-pin').focus()" style="cursor:pointer">
        <div class="acc-av">${a.holder.split(' ').map(w=>w[0]).join('').slice(0,2)}</div>
        <div>
          <div class="acc-n">${a.holder}</div>
          <div class="acc-no">Acc: ${a.number}</div>
        </div>
      </div>`).join('');
    wrap.style.display='block';
  }else{
    wrap.style.display='none';
  }
}

/* ── LOGIN ──────────────────────────────────── */
async function doLogin(){
  const account=$('l-acc').value.trim();
  const pin=$('l-pin').value.trim();
  if(!account||!pin){toast('t-login','Enter account number and PIN.','err');return;}
  const res=await api('/api/login',{account,pin});
  if(res.ok){
    $('dash-hi').textContent='Hello, '+res.holder.split(' ')[0]+' 👋';
    $('d-bal').textContent=fmt(res.balance);
    $('d-name').textContent=res.holder;
    $('d-acc').textContent='•••• '+res.account.slice(-4);
    $('ftr').textContent='SESSION ACTIVE  ·  '+res.holder.toUpperCase();
    $('l-pin').value=''; syncDots('');
    go('pg-dash');
  }else{
    toast('t-login',res.msg,'err');
  }
}

/* ── LOGOUT ─────────────────────────────────── */
async function doLogout(){
  await api('/api/logout');
  $('l-acc').value=''; $('l-pin').value=''; syncDots('');
  $('ftr').textContent='SECURE CONNECTION ESTABLISHED';
  go('pg-welcome');
}

/* ── BALANCE ────────────────────────────────── */
async function doBalance(){
  const res=await api('/api/balance');
  if(res.ok){
    $('b-amt').textContent=fmt(res.balance);
    $('b-name').textContent=res.holder;
    $('b-acc').textContent='•••• '+res.account.slice(-4);
    $('b-time').textContent='As of '+new Date().toLocaleString();
    $('d-bal').textContent=fmt(res.balance);
    go('pg-bal');
  }
}

/* ── DEPOSIT ────────────────────────────────── */
async function doDeposit(){
  const amount=parseFloat($('inp-dep').value);
  if(!amount||amount<=0){toast('t-dep','Enter a valid amount.','err');return;}
  const res=await api('/api/deposit',{amount});
  toast('t-dep',res.msg, res.ok?'ok':'err');
  if(res.ok){
    $('d-bal').textContent=fmt(res.balance);
    $('inp-dep').value='';
    setTimeout(()=>go('pg-dash'),1800);
  }
}

/* ── WITHDRAW ───────────────────────────────── */
async function doWithdraw(){
  const amount=parseFloat($('inp-wd').value);
  if(!amount||amount<=0){toast('t-wd','Enter a valid amount.','err');return;}
  const res=await api('/api/withdraw',{amount});
  toast('t-wd',res.msg, res.ok?'ok':'err');
  if(res.ok){
    $('d-bal').textContent=fmt(res.balance);
    $('inp-wd').value='';
    setTimeout(()=>go('pg-dash'),1800);
  }
}

/* ── HISTORY ────────────────────────────────── */
async function doHistory(){
  const res=await api('/api/history');
  const el=$('hist-list');
  const icons={deposit:'↑',withdraw:'↓',balance:'◈'};
  if(!res.ok||!res.history.length){
    el.innerHTML='<div style="color:var(--white-faint);font-size:13px;text-align:center;padding:24px 0;font-family:var(--mono)">No transactions yet</div>';
  }else{
    el.innerHTML=res.history.slice().reverse().map(t=>`
      <div class="tx">
        <div class="tx-ic ${t.kind}">${icons[t.kind]||'·'}</div>
        <div class="tx-info">
          <div class="tx-k">${t.kind}</div>
          <div class="tx-t">${t.time}</div>
        </div>
        <div>
          <div class="tx-v ${t.kind}">
            ${t.kind==='balance'?fmt(t.balance):(t.kind==='deposit'?'+':'-')+fmt(t.amount)}
          </div>
          <div class="tx-b">Bal: ${fmt(t.balance)}</div>
        </div>
      </div>`).join('');
  }
  go('pg-hist');
}

/* ── keyboard shortcuts ─────────────────────── */
document.addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    const on=document.querySelector('.pg.on');
    if(on.id==='pg-login') doLogin();
    if(on.id==='pg-register') doRegister();
    if(on.id==='pg-deposit') doDeposit();
    if(on.id==='pg-withdraw') doWithdraw();
  }
});
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

PORT = 8080

def start():
    print("\n  Pacer Bank Limited ATM — Starting...")
    print(f"  Open: http://localhost:{PORT}\n")
    server = http.server.HTTPServer(("", PORT), ATMHandler)
    threading.Timer(0.6, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ATM shut down.\n")

if __name__ == "__main__":
    start()
