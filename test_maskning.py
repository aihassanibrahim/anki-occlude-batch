#!/usr/bin/env python3
"""
Snabb test-script för att testa olika maskningspositioner
"""

import os
import sys
import subprocess

def test_maskning(top_perc, bot_perc, skip_pages=3):
    """Testa maskning med specifika procentvärden"""
    cmd = [
        "python3", "maska_ratt_svar.py",
        "Rest Tentamen - Basvetenskap 3 - VT2022.pdf",
        "out/",
        "--skip-pages", str(skip_pages),
        "--mode", "column",
        "--col-top-perc", str(top_perc),
        "--col-bot-perc", str(bot_perc),
        "--build-apkg"
    ]
    
    print(f"🧪 Testar: top={top_perc}%, bottom={bot_perc}%")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Klar! PDF: out/tenta_maskad.pdf")
            print(f"📦 Anki: bv3_maskad.apkg")
        else:
            print(f"❌ Fel: {result.stderr}")
    except Exception as e:
        print(f"❌ Fel: {e}")

def main():
    if len(sys.argv) == 3:
        # Använd kommandoradsargument
        top = float(sys.argv[1])
        bot = float(sys.argv[2])
        test_maskning(top, bot)
    else:
        # Interaktivt läge
        print("🎯 Maskningstest - Ange procentvärden")
        print("Format: top% bottom% (t.ex. 20 65)")
        print("Eller kör: python3 test_maskning.py 20 65")
        
        try:
            user_input = input("Ange top% och bottom%: ").strip()
            if user_input:
                parts = user_input.split()
                if len(parts) >= 2:
                    top = float(parts[0])
                    bot = float(parts[1])
                    test_maskning(top, bot)
                else:
                    print("❌ Ange både top% och bottom%")
        except KeyboardInterrupt:
            print("\n👋 Avbrutet")
        except Exception as e:
            print(f"❌ Fel: {e}")

if __name__ == "__main__":
    main()

