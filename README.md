# Personal Time Tracker

Lični time tracker za Windows laptop, po uzoru na Clockify (tajmer, projekti, izveštaji) i Time Doctor (automatsko praćenje aplikacija, detekcija neaktivnosti, screenshotovi). Sve radi lokalno: nema naloga, servera ni slanja podataka bilo kome.

## Šta ume

**Kao Clockify**
- Tajmer sa opisom, projektom i oznakom "naplativo". Enter u polju za opis pokreće tajmer, `Ctrl+Space` ga pali i gasi.
- Opis i projekat možeš menjati dok tajmer radi.
- Predlozi iz ranijih opisa dok kucaš (izbor predloga postavlja i projekat).
- Ručni unosi, izmena, dupliranje, brisanje i "Nastavi" (ponovo pokreće isti zadatak). `Ctrl+N` dodaje ručni unos.
- Unosi grupisani po danima sa dnevnim zbirom.
- Projekti sa bojom, satnicom i arhiviranjem.
- Izveštaji za danas, juče, ovu i prošlu nedelju, ovaj i prošli mesec, godinu ili proizvoljan period: ukupno, naplativo, zarada, prosek po danu, grafikon po danu sa dnevnim ciljem, raspodela po projektu i po zadatku.
- Izvoz u CSV koji Excel otvara direktno (UTF-8, tačka-zarez, decimalni zarez).

**Kao Time Doctor**
- Detekcija neaktivnosti: posle N minuta bez tastature i miša pita da li da odbaci to vreme (i nastavi ili zaustavi tajmer) ili da ga zadrži.
- Zatvaranje poklopca (sleep/hibernacija) se prepoznaje kao neaktivnost.
- Praćenje aktivne aplikacije i naslova prozora (samo dok radi tajmer, uvek, ili isključeno). Kartica "Aktivnost" pokazuje koliko si vremena proveo u kojoj aplikaciji i prozoru, i koliki deo rada za računarom je pokriven tajmerom.
- Screenshotovi na zadati interval (podrazumevano isključeni), sa automatskim brisanjem posle N dana.
- Podsetnik kad radiš a tajmer nije pokrenut, i upozorenje kad tajmer radi predugo.

**Windows**
- Ikonica u tray-u (pored sata): zelena dok tajmer radi, meni za start/stop i izlaz. Zatvaranje prozora sklanja aplikaciju u tray.
- Opcija "Pokreni sa Windows-om".
- Tajmer preživljava zatvaranje aplikacije i restart računara (vreme se računa od početka).
- Rezervna kopija baze iz Podešavanja.

## Instalacija

### Varijanta A: gotov .exe (bez Pythona)

1. Na GitHub-u otvori **Actions → Test and build → poslednji uspešan run**.
2. Preuzmi artifact **PersonalTimeTracker-windows** i raspakuj `PersonalTimeTracker.exe`.
3. Pokreni ga. Windows SmartScreen će verovatno upozoriti jer exe nije potpisan: **More info → Run anyway**.

Ako napraviš tag `v1.0.0` i pushuješ ga, exe se automatski kači i na GitHub Release.

### Varijanta B: iz izvornog koda

1. Instaliraj Python 3.10+ sa [python.org](https://www.python.org/downloads/windows/) (čekiraj "Add python.exe to PATH").
2. Dvoklik na `run.bat` (instalira Pillow i pystray, pa pokreće aplikaciju bez konzole).

Sam svoj exe praviš sa `build.bat` (rezultat je `dist\PersonalTimeTracker.exe`).

## Gde su podaci

`%APPDATA%\PersonalTimeTracker\`
- `timetracker.db`: SQLite baza (unosi, projekti, aktivnost)
- `settings.json`: podešavanja
- `screenshots\`: screenshotovi po danima

Putanju možeš promeniti promenljivom okruženja `PTT_DATA_DIR`.

## Razvoj

```
pip install -r requirements-dev.txt
python -m pytest -q          # na Linuxu UI testovi traže ekran: xvfb-run -a python -m pytest -q
python -m timetracker        # pokretanje
```

Struktura:

| Fajl | Uloga |
|---|---|
| `timetracker/db.py` | SQLite šema i operacije |
| `timetracker/tracker.py` | pozadinska nit: neaktivnost, sleep, aplikacije, screenshotovi, podsetnici |
| `timetracker/platform_win.py` | Windows API preko ctypes (idle vreme, aktivni prozor, mutex, autostart) |
| `timetracker/reports.py` | zbirovi, raspodele i CSV izvoz |
| `timetracker/ui/` | tkinter interfejs |
| `tests/` | testovi jezgra, UI smoke testovi i testovi pravih Windows poziva (na Windows CI) |

## Poznata ograničenja

- Za sajtove se beleži samo naslov prozora pregledača (npr. "GitHub - Google Chrome"), ne URL.
- Windows Store (UWP) aplikacije se mogu pojaviti kao `ApplicationFrameHost`; naslov prozora je i dalje tačan.
- Ako izađeš iz aplikacije dok tajmer radi, vreme se i dalje računa, ali se neaktivnost i aplikacije ne prate dok je ponovo ne pokreneš.
- Exe nije potpisan, pa SmartScreen i ponekad antivirus reaguju na prvo pokretanje.
