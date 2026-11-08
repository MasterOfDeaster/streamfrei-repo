# Nuvio TV B2

Veränderte Fassung von [Nuvio TV](https://github.com/NuvioMedia/NuvioTVSmart) (GPL-3.0),
abgestimmt auf den **LG OLED55B29LA** mit **webOS TV 23 (8.3.0, Chromium 94)**.
Wird als eigene App `space.nuvio.webosb2` installiert, die offizielle Nuvio-App bleibt daneben bestehen.

## Was anders ist

- **Für Chromium 94 übersetzt** statt für Chromium 56: Der Code des Fernsehers wird direkt
  ausgeführt statt über ältere Ersatzkonstrukte (Haupt-Bundle 3,73 → 3,48 MB, Polyfills 153 → 100 KB).
  Auf älteren Fernsehern meldet die App beim Start, dass sie nicht unterstützt wird.
- **Sparsamer Modus für LG-Geräte mit α5/α7-Chip** (OLED A, OLED B1–B3, UHD/NanoCell-LCD).
  Der B2 hat einen α7 Gen5. Die offizielle App stuft ihn nach Baujahr als „modern“ ein und
  zeigt deshalb alle Effekte. Hier bekommt er wie ältere TVs:
  - keine Unschärfe-Ebenen (backdrop-filter) hinter der Seitenleiste,
  - nur eine Hintergrundbild-Ebene statt Überblendung zweier Vollbilder,
  - kurze Einblendung statt gleitender Seitenwechsel-Animationen,
  - sofortiges Zuklappen der Poster ohne überlappende Animationen,
  - gebremste Wiederholung beim Gedrückthalten der Pfeiltasten, damit sich keine Eingaben stauen,
  - seltener gespeicherten Wiedergabe-Fortschritt.
  Das Layout bleibt das moderne, Funktionen fallen nicht weg.

## Dateien

- `nuvio-b2.patch`: Quellcode-Änderung gegenüber NuvioTVSmart `bd73c02f7fa95542485ae108a1eb5f3cc63d3a66`
- `build-nuvio-b2.py`: baut die IPK (Patch, Build mit `NUVIO_CHROMIUM_TARGET=94`, neue App-ID)

```bash
git clone https://github.com/NuvioMedia/NuvioTVSmart && git -C NuvioTVSmart checkout bd73c02f7fa95542485ae108a1eb5f3cc63d3a66
curl -LO https://github.com/NuvioMedia/NuvioTVSmart/releases/download/1.3.9/NuvioTV-webOS-1.3.9.ipk
python3 build-nuvio-b2.py NuvioTVSmart NuvioTV-webOS-1.3.9.ipk out
```

Die offizielle Release-IPK liefert nur `nuvio.env.js` (öffentliche Dienst-Schlüssel), die im Quellcode nicht enthalten ist.
