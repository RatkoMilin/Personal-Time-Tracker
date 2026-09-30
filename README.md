# Personal Time Tracker

Mali lični time tracker za Windows koji izgleda kao stari Winamp: zeleni LCD tajmer, dugmad PLAY / PAUZA / STOP i "plejlista" današnjih unosa. Sve je lokalno: nema naloga, servera ni slanja podataka.

## Kako se koristi

1. Upiši **zadatak** (i po želji **projekat**) i pritisni **▶** ili Enter.
2. **❚❚** pauzira; ponovni klik nastavlja isti zadatak.
3. **■** zaustavlja i briše polja.
4. **PL** prikazuje ili sakriva listu unosa za dan (strelice menjaju dan).
   - dvoklik na unos: nastavi taj zadatak
   - Enter ili **IZMENI**: promeni vreme, naziv ili projekat
   - Delete ili **OBRIŠI**: obriši
   - **+ DODAJ**: ručno dodaj vreme koje si zaboravio da pokreneš
5. **⏏** izvozi CSV za Excel (ova nedelja, prošla nedelja, mesec...).

Desni klik bilo gde (ili kvadratić gore levo) otvara meni: neaktivnost, uvek na vrhu, pokretanje sa Windows-om, izvoz, folder sa podacima, izlaz.

`Ctrl+Space` pali i pauzira tajmer.

**Neaktivnost:** ako tajmer radi, a ti nisi dirao tastaturu i miš duže od 5 minuta (ili si zatvorio laptop), po povratku te pita da li to vreme da odbaci ili zadrži.

**Tray:** zatvaranje prozora sklanja aplikaciju pored sata; tajmer radi dalje. Izlaz je u meniju.

## Instalacija

### Gotov .exe (bez Pythona)

1. Na GitHub-u: **Actions → Test and build → poslednji uspešan run**.
2. Preuzmi **PersonalTimeTracker-windows** i raspakuj `PersonalTimeTracker.exe`.
3. Pokreni. SmartScreen će upozoriti jer exe nije potpisan: **More info → Run anyway**.

### Iz izvornog koda

1. Instaliraj Python 3.10+ sa [python.org](https://www.python.org/downloads/windows/) (čekiraj "Add python.exe to PATH").
2. Dvoklik na `run.bat`.

Svoj exe praviš sa `build.bat` (rezultat: `dist\PersonalTimeTracker.exe`).

## Podaci

`%APPDATA%\PersonalTimeTracker\timetracker.db` (SQLite) i `settings.json`. Putanju menja promenljiva `PTT_DATA_DIR`.

## Razvoj

```
pip install -r requirements-dev.txt
python -m pytest -q        # na Linuxu: xvfb-run -a python -m pytest -q
python -m timetracker
```

| Fajl | Uloga |
|---|---|
| `timetracker/db.py` | SQLite: projekti i unosi |
| `timetracker/tracker.py` | pozadinska provera neaktivnosti i sleep-a |
| `timetracker/platform_win.py` | Windows API preko ctypes (idle vreme, jedna instanca, autostart) |
| `timetracker/reports.py` | zbirovi i CSV |
| `timetracker/ui/skin.py` | Winamp izgled: LCD cifre, marquee, dugmad |
| `timetracker/ui/player.py` | glavni prozor i plejlista |
| `timetracker/ui/dialogs.py` | izmena unosa i pitanje za neaktivnost |
