# Personal Time Tracker

Mali lični time tracker za Windows koji izgleda kao stari Winamp: LCD tajmer, dugmad PLAY / PAUZA / STOP i "plejlista" današnjih unosa. Sve je lokalno: nema naloga, servera ni slanja podataka.

## Skinovi

Desni klik → **Skin**:

| Skin | Izgled |
|---|---|
| Matrix (digitalni) | klasični Winamp: zelene LCD cifre na crnom, 3D dugmad |
| Pastel (roze-plavi) | mekan: zaobljene ivice, zaobljene cifre, roze i svetloplava |
| Drvo (analogni) | miran i najjednostavniji: drveni okvir, tamnozeleni panel, analogni sat sa kazaljkama umesto cifara |
| Sajber (sivi) | oštar: odsečeni uglovi, iskošene cifre, siva sa cijan linijama |

Svaki skin ima svoje zvučne efekte za start, pauzu, stop, klik i podsetnik: Matrix digitalne pištaljke, Pastel mehuriće, Drvo kucanje u drvo, Sajber zvuk mača (izvlačenje, zamah, zvek). Zvuci se prave u kodu (`timetracker/sounds.py`), nema audio fajlova. Isključuju se u meniju: **Zvučni efekti**. Podsetnik za neaktivnost i tada pusti sistemski zvuk.

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

Desni klik bilo gde (ili dugmence gore levo) otvara meni: skin, podsetnik za neaktivnost, uvek na vrhu, pokretanje sa Windows-om, izvoz, folder sa podacima, izlaz.

`Ctrl+Space` pali i pauzira tajmer.

**Podsetnik za neaktivnost:** ako tajmer radi, a ti 5 minuta ne dirneš tastaturu ni miš, odmah iskoči prozor (uvek na vrhu, sa zvukom) koji broji koliko te nema. Kad se vratiš, prozor zamrzne to vreme i pita: **Odbaci** (tajmer nastavlja bez tog vremena), **Odbaci i stani** ili **Zadrži**. Isto važi i posle zatvaranja laptopa. Granica (5, 10, 15, 30 min ili isključeno) se menja u meniju.

**Tray:** zatvaranje prozora sklanja aplikaciju pored sata; tajmer radi dalje. Izlaz je u meniju.

## Na telefonu

Postoji i web verzija za telefon (folder `web/`): isti izgled, sva 4 skina i zvuci, lista unosa, CSV izvoz. Radi i bez interneta.

**Adresa:** https://ratkomilin.github.io/Personal-Time-Tracker/

- **iPhone (Safari):** otvori adresu → dugme Deli (kvadrat sa strelicom) → **Add to Home Screen**.
- **Android (Chrome):** otvori adresu → meni ⋮ → **Install app** ili **Add to Home screen**.

Posle toga se otvara kao obična aplikacija, preko celog ekrana.

Podaci na telefonu su **odvojeni** od laptopa i čuvaju se samo u tom telefonu. Rezervnu kopiju pravi meni ☰ → Rezervna kopija → Sačuvaj; tu je i CSV izvoz (i za "Sve"). Na telefonu nema podsetnika za neaktivnost, jer telefon ne dozvoljava aplikaciji da prati da li ga koristiš dok je u pozadini. Tajmer i dalje ispravno računa vreme kad zatvoriš aplikaciju ili zaključaš ekran.

Objava na tu adresu ide automatski (GitHub Actions, "Mobile web app") posle svake izmene u `web/` na grani main. Jednom treba uključiti: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Instalacija

### Gotov .exe (bez Pythona)

1. Na GitHub-u otvori **Releases** i preuzmi `PersonalTimeTracker.exe` iz poslednjeg izdanja.
   (Najnoviji build bilo koje grane: **Actions → Test and build → run → Artifacts**, zip sa exe-om.)
2. Stavi exe u stalan folder (ne u Downloads), jer "Pokreni sa Windows-om" pamti njegovu putanju.
3. Pokreni. SmartScreen će upozoriti jer exe nije potpisan: **More info → Run anyway**.

### Iz izvornog koda

1. Instaliraj Python 3.10+ sa [python.org](https://www.python.org/downloads/windows/) (čekiraj "Add python.exe to PATH").
2. Dvoklik na `run.bat`.

Svoj exe praviš sa `build.bat` (rezultat: `dist\PersonalTimeTracker.exe`).

Novo izdanje: **Releases → Draft a new release**, upiši oznaku (npr. `v1.1.0`) i objavi; GitHub Actions napravi exe i okači ga na izdanje.

## Podaci

`%APPDATA%\PersonalTimeTracker\timetracker.db` (SQLite) i `settings.json`. Putanju menja promenljiva `PTT_DATA_DIR`.

## Razvoj

```
pip install -r requirements-dev.txt
python -m pytest -q        # na Linuxu: xvfb-run -a python -m pytest -q
pip install playwright && python -m playwright install chromium   # za testove web verzije
python -m timetracker
```

| Fajl | Uloga |
|---|---|
| `timetracker/db.py` | SQLite: projekti i unosi |
| `timetracker/tracker.py` | pozadinska provera neaktivnosti i sleep-a (IdleStart / IdleEnd) |
| `timetracker/platform_win.py` | Windows API preko ctypes (idle vreme, jedna instanca, autostart) |
| `timetracker/reports.py` | zbirovi i CSV |
| `timetracker/sounds.py` | sintetizovani zvučni efekti po skinu |
| `timetracker/ui/skin.py` | teme i iscrtani elementi: paneli, dugmad, LCD cifre, analogni sat |
| `timetracker/ui/player.py` | glavni prozor i plejlista |
| `timetracker/ui/dialogs.py` | izmena unosa i podsetnik za neaktivnost |
| `web/` | mobilna web verzija (HTML/CSS/JS, bez biblioteka), testovi u `tests/test_web.py` |
