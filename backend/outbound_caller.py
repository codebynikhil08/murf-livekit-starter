"""
Kisan Mitra — Outbound Price Alert Caller (Day 6)
==================================================
Calls a farmer when their crop's mandi price crosses their target threshold.

Usage (from backend/ directory):
    uv run python outbound_caller.py
    uv run python outbound_caller.py --phone +918758329927 --farmer "Ramesh" --crop cotton --district Yavatmal --threshold 7000
    uv run python outbound_caller.py --dry-run     # Print plan without calling

Outcome handling: no-answer → retry in 2h | busy → retry in 15m | hang-up < 5s → opt-out
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
backend_dir = Path(__file__).parent
src_dir = backend_dir / "src"
for p in (str(src_dir), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(backend_dir / ".env.local")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kisan-outbound")

# ── Config ────────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
FARMER_PHONE_NUMBER = os.getenv("FARMER_PHONE_NUMBER")
NGROK_AUTH_TOKEN    = os.getenv("NGROK_AUTH_TOKEN")  # optional

# Global alert state — filled in main() before server starts
ALERT: dict = {}
RETRY_LOG: dict = {}   # call_sid → retry info

# ── Flask Webhook App ─────────────────────────────────────────────────────────
from flask import Flask, Response, request
from twilio.twiml.voice_response import Gather, Hangup, VoiceResponse

flask_app = Flask("kisan-mitra-outbound")


def _make_alert_twiml(action_url: str) -> str:
    """
    Returns TwiML for the initial alert call.
    Day 6 rule: first 2 sentences → who is calling, why, and how to stop.
    """
    a = ALERT
    response = VoiceResponse()

    # ── Opening (Day 6 compliant) ──────────────────────────────────────────
    # Sentence 1: Who & why
    # Sentence 2: How to stop
    opening = (
        f"Namaste {a.get('farmer_name', 'kisan')} ji! "
        f"Main Kisan Mitra bol raha hoon — aapki fasal sahayata seva. "
        f"Aaj {a.get('market', 'aapki mandi')} mein "
        f"{a.get('crop', 'aapki fasal').capitalize()} ka bhav "
        f"{a.get('current_price', 0)} rupaye per {a.get('unit', 'quintal')} hai, "
        f"jo aapke target {a.get('target_price', 0)} rupaye se oopar gaya hai. "
        f"Yeh aapke liye khushkhabri hai! "
        f"Agar aap yeh calls nahi chahte, toh abhi 9 dabayein. "
        f"Adhik bhav ki jaankari ke liye 1 dabayein."
    )

    gather = Gather(
        num_digits=1,
        action=action_url,
        timeout=10,
        method="POST",
    )
    gather.say(opening, language="hi-IN", voice="Polly.Aditi")
    response.append(gather)

    # No input → polite goodbye
    response.say(
        "Koi input nahi mili. Dhanyavaad aur achi fasal ki shubhkamnayein! "
        "Kisan Mitra ki taraf se namaste.",
        language="hi-IN",
        voice="Polly.Aditi",
    )
    response.hangup()
    return str(response)


@flask_app.route("/twiml/alert", methods=["GET", "POST"])
def alert_twiml():
    logger.info("Twilio hit /twiml/alert")
    action_url = request.url_root.rstrip("/") + "/twiml/keypress"
    return Response(_make_alert_twiml(action_url), mimetype="application/xml")


@flask_app.route("/twiml/keypress", methods=["POST"])
def handle_keypress():
    """Handle farmer's key press: 1 = more info, 9 = opt-out, other = goodbye."""
    digit = request.form.get("Digits", "")
    a = ALERT
    logger.info(f"Farmer pressed: {digit!r}")

    response = VoiceResponse()

    if digit == "1":
        detail = (
            f"{a.get('market', 'mandi')} ki aaj ki poori jaankari yeh hai. "
            f"{a.get('crop', 'fasal').capitalize()} ka modal bhav "
            f"{a.get('current_price', 0)} rupaye per {a.get('unit', 'quintal')} hai. "
            f"Minimum bhav {a.get('min_price', 'N/A')} aur maximum {a.get('max_price', 'N/A')} rupaye hai. "
            f"Aaj mandi jaane ke liye bilkul sahi samay hai. "
            f"Kisan Mitra hamesha aapke saath hai. Dhanyavaad aur namaste!"
        )
        response.say(detail, language="hi-IN", voice="Polly.Aditi")

    elif digit == "9":
        response.say(
            "Bilkul theek hai. Hum aapko aur calls nahi karenge. "
            "Agar kabhi koi sawaal ho toh Kisan Mitra app pe aayein. "
            "Dhanyavaad, namaste!",
            language="hi-IN",
            voice="Polly.Aditi",
        )
        logger.info(f"Farmer {a.get('farmer_name')} opted out — marking in log.")
        RETRY_LOG["opted_out"] = True

    else:
        response.say(
            "Koi baat nahi. Kisan Mitra ki taraf se dhanyavaad. "
            "Achi fasal aur achi kamai ki shubhkamnayein! Namaste.",
            language="hi-IN",
            voice="Polly.Aditi",
        )

    response.hangup()
    return Response(str(response), mimetype="application/xml")


@flask_app.route("/twiml/status", methods=["POST"])
def call_status():
    """
    Twilio calls this when call ends. Handles all 4 outbound outcomes:
      • no-answer → retry in 2 hours
      • busy      → retry in 15 minutes
      • completed < 5s → immediate hang-up (opted out)
      • completed ≥ 5s → success
    """
    status   = request.form.get("CallStatus", "unknown")
    sid      = request.form.get("CallSid", "?")
    duration = int(request.form.get("CallDuration", "0"))

    logger.info(f"📞 Call {sid} status={status!r} duration={duration}s")

    timestamp = datetime.now().strftime("%H:%M:%S")

    if status == "no-answer":
        logger.warning(f"[{timestamp}] No answer. Retry scheduled in 2 hours.")
        RETRY_LOG[sid] = {"outcome": "no-answer", "retry_after_min": 120}

    elif status == "busy":
        logger.warning(f"[{timestamp}] Line busy. Retry scheduled in 15 minutes.")
        RETRY_LOG[sid] = {"outcome": "busy", "retry_after_min": 15}

    elif status == "failed":
        logger.error(f"[{timestamp}] Call failed. Check Twilio logs for SID {sid}.")
        RETRY_LOG[sid] = {"outcome": "failed", "retry_after_min": 60}

    elif status == "completed" and duration < 5:
        logger.info(f"[{timestamp}] Immediate hang-up (<5s). Marking as opted-out for 24h.")
        RETRY_LOG[sid] = {"outcome": "immediate-hangup", "retry_after_min": 1440}

    elif status == "completed":
        logger.info(f"[{timestamp}] ✅ Call completed successfully ({duration}s). Alert delivered!")
        RETRY_LOG[sid] = {"outcome": "success", "duration_s": duration}

    return Response("", status=204)


# ── Price Check ───────────────────────────────────────────────────────────────
def check_price_alert(crop: str, district: str, threshold: float, farmer_name: str) -> dict | None:
    """
    Look up today's mandi price for (crop, district).
    Returns alert dict if price >= threshold, else None.
    """
    try:
        from tools import MANDI_PRICE_DATABASE
    except ImportError:
        from src.tools import MANDI_PRICE_DATABASE

    crop_key     = crop.lower().strip()
    district_key = district.lower().strip()

    crop_data = MANDI_PRICE_DATABASE.get(crop_key)
    if not crop_data:
        # Partial match
        for k, v in MANDI_PRICE_DATABASE.items():
            if crop_key in k or k in crop_key:
                crop_data = v
                crop_key = k
                break

    if not crop_data:
        logger.warning(f"No price data for crop '{crop}'")
        return None

    dist_data = crop_data.get(district_key)
    if not dist_data:
        for k, v in crop_data.items():
            if district_key in k or k in district_key:
                dist_data = v
                break

    if not dist_data:
        # Use first available market as fallback
        dist_data = list(crop_data.values())[0]
        logger.info(f"Using fallback market: {dist_data['market']}")

    modal_price = dist_data["modal"]
    logger.info(
        f"Price check: {crop} in {district} → ₹{modal_price}/quintal "
        f"(threshold ₹{threshold})"
    )

    if modal_price >= threshold:
        return {
            "farmer_name": farmer_name,
            "crop":         crop_key,
            "district":     district,
            "current_price": modal_price,
            "target_price":  int(threshold),
            "min_price":     dist_data["min"],
            "max_price":     dist_data["max"],
            "unit":          dist_data["unit"],
            "market":        dist_data["market"],
        }
    return None


# ── Call Initiator ────────────────────────────────────────────────────────────
def place_call(public_url: str, to_number: str) -> str | None:
    """Initiate the outbound Twilio call and return call SID."""
    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    alert_url  = public_url.rstrip("/") + "/twiml/alert"
    status_url = public_url.rstrip("/") + "/twiml/status"

    call = client.calls.create(
        url=alert_url,
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        status_callback=status_url,
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
        method="POST",
        timeout=30,          # ring for 30s before no-answer
    )

    logger.info(f"Call placed! SID: {call.sid} → {to_number}")
    return call.sid


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Kisan Mitra Outbound Price Alert Caller (Day 6)"
    )
    parser.add_argument("--phone",     default=FARMER_PHONE_NUMBER, help="Number to call (E.164)")
    parser.add_argument("--farmer",    default="Ramesh",            help="Farmer name")
    parser.add_argument("--crop",      default="cotton",            help="Crop name")
    parser.add_argument("--district",  default="Yavatmal",          help="District/market")
    parser.add_argument("--threshold", type=float, default=7000,    help="Target price (₹/quintal)")
    parser.add_argument("--port",      type=int,   default=5055,    help="Local Flask port")
    parser.add_argument("--dry-run",   action="store_true",         help="Show plan, don't call")
    args = parser.parse_args()

    # ── Validate credentials ──────────────────────────────────────────────
    missing = [k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER")
               if not os.getenv(k)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        print("   Add them to backend/.env.local")
        sys.exit(1)

    if not args.phone:
        print("❌ No phone number. Use --phone +91XXXXXXXXXX or set FARMER_PHONE_NUMBER in .env.local")
        sys.exit(1)

    # ── Check price alert ─────────────────────────────────────────────────
    print(f"\n🌾  Checking {args.crop.capitalize()} price in {args.district}...")
    alert_data = check_price_alert(args.crop, args.district, args.threshold, args.farmer)

    if not alert_data:
        print(f"   ℹ️  Price has NOT crossed threshold (₹{args.threshold}). No call needed today.")
        print(f"   Use --threshold with a lower value to force a demo call.")
        sys.exit(0)

    # ── Fill global alert state ───────────────────────────────────────────
    ALERT.update(alert_data)

    # ── Print summary ─────────────────────────────────────────────────────
    print(f"\n{'═'*55}")
    print(f"  🌾  KISAN MITRA — OUTBOUND PRICE ALERT")
    print(f"{'═'*55}")
    print(f"  Farmer    : {alert_data['farmer_name']}")
    print(f"  Crop      : {alert_data['crop'].capitalize()}")
    print(f"  Market    : {alert_data['market']}")
    print(f"  Price Now : ₹{alert_data['current_price']}/quintal")
    print(f"  Target    : ₹{alert_data['target_price']}/quintal")
    print(f"  Calling   : {args.phone}")
    print(f"  Time      : {datetime.now().strftime('%d %b %Y %I:%M %p')}")
    print(f"{'═'*55}")

    if args.dry_run:
        print("\n  [DRY RUN] No call placed. Remove --dry-run to make the real call.")
        print(f"\n  Opening message preview:")
        print(f"  \"Namaste {alert_data['farmer_name']} ji! Main Kisan Mitra bol raha hoon —")
        print(f"   aapki fasal sahayata seva. Aaj {alert_data['market']} mein")
        print(f"   {alert_data['crop'].capitalize()} ka bhav {alert_data['current_price']} rupaye")
        print(f"   per {alert_data['unit']} hai, jo aapke target {alert_data['target_price']}")
        print(f"   rupaye se oopar gaya hai. Yeh aapke liye khushkhabri hai!")
        print(f"   Agar aap yeh calls nahi chahte, toh abhi 9 dabayein.\"")
        sys.exit(0)

    # ── Start Flask webhook server in background thread ───────────────────
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0",
            port=args.port,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
        name="flask-webhook",
    )
    flask_thread.start()
    time.sleep(1.5)  # Let Flask warm up

    # ── Start ngrok tunnel ────────────────────────────────────────────────
    try:
        from pyngrok import ngrok, conf

        if NGROK_AUTH_TOKEN:
            conf.get_default().auth_token = NGROK_AUTH_TOKEN

        print(f"\n🔗  Starting ngrok tunnel on port {args.port}...")
        tunnel = ngrok.connect(args.port, "http")
        public_url = tunnel.public_url
        # Force HTTPS
        if public_url.startswith("http://"):
            public_url = "https://" + public_url[7:]
        print(f"   ✅ Public URL: {public_url}")

    except Exception as e:
        print(f"\n❌ ngrok failed: {e}")
        print("   Try: pip install pyngrok  OR  set NGROK_AUTH_TOKEN in .env.local")
        print("   Alternative: run 'ngrok http 5055' in another terminal,")
        print("   then re-run with --ngrok-url https://xxxx.ngrok.io")
        sys.exit(1)

    # ── Place the call ────────────────────────────────────────────────────
    print(f"\n📞  Calling {args.phone} via Twilio...")
    try:
        call_sid = place_call(public_url, args.phone)
        print(f"   ✅ Call initiated! SID: {call_sid}")
        print(f"\n   👀 Your phone ({args.phone}) should ring in ~5 seconds.")
        print(f"   📱 Pick up → listen to the price alert → press 1 for details / 9 to opt-out")
        print(f"\n{'─'*55}")
        print(f"   Webhook server running. Press Ctrl+C to stop.\n")

    except Exception as e:
        print(f"\n❌ Twilio call failed: {e}")
        print("   Common causes:")
        print("   • Your personal number is not verified on Twilio (free trial limit)")
        print("     → Go to console.twilio.com → Phone Numbers → Verified Caller IDs")
        print("   • Wrong Account SID or Auth Token")
        sys.exit(1)

    # ── Keep alive while call plays ───────────────────────────────────────
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋  Shutting down Kisan Mitra outbound server.")
        # Print outcome summary
        if RETRY_LOG:
            print("\n📊  Call Outcome Summary:")
            for k, v in RETRY_LOG.items():
                print(f"   {k}: {v}")
        try:
            ngrok.kill()
        except Exception:
            pass


if __name__ == "__main__":
    main()
