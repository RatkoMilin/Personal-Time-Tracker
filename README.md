# Personal Time Tracker

Mali lični time tracker za Windows koji izgleda kao stari Winamp: LCD tajmer, dugmad PLAY / PAUZA / STOP i "plejlista" današnjih unosa. Sve je lokalno: nema naloga, servera ni slanja podataka.

## Skinovi

Desni klik → **Skin**:

| Skin | Izgled |
|---|---|
| Matrix | klasični Winamp: zelene LCD cifre na crnom, 3D dugmad; na start i pauzu cifre se na trenutak izmešaju kao pokvaren sat |
| Pastel | mekan: zaobljene ivice, zaobljene cifre, roze i svetloplava; kad otvoriš PL, preko liste se dižu i pucaju mehurići |
| Orah | miran: okvir od orahovog drveta, tamnozeleni panel, analogni sat; produktivnost je grana koja procveta, a klik na cvet ga pretvara u orah (ostaje orah do sutra) |
| Samuraj | oštar: srebrni oklop, odsečeni uglovi, iskošene neonsko plave cifre; produktivnost je katana čije sečivo svetli neonsko plavo, sa sjajem oko plavog dela |
| Mačkasti | krem bela i tamno siva: mačje uši, dugmići su šapice, pegava PL lista; na 80%+ produktivnosti na traci leži debela bela maca, a klik na nju: mrda repom, okrene se i trepne ili udari šapicom (nasumičnim redom) |
| Setsuna | #DB4C01, #E94C53, bela i crna: okrugla dugmad, listovi narandže u PL; na start konfete preko cele aplikacije, dok tajmer radi pored naslova se ređaju narandže (četvrt posle 15 min, pola posle 30, cela za svaki sat); produktivnost su japanski lampioni koji se pale |
| Mondrian | bela sa debelim crnim linijama i osnovnim bojama #dd0100, #225095, #fac901: crvena PL lista, plavo polje za zadatak i PLAY, žuta produktivnost |
| Maslačak | preliv bele, pastel roze i svetlo zelene, dugmići su suptilni cvetovi; desno preko celog prozora maslačak sa 24 latice koji je sat: u podne su sve žute, svaki sat po dve postanu siva semena, a od 00:00 do 01:00 klikom ga oduvaš (seme se razleti, a gospodin sa cilindrom i brkovima, koji se drži za stabljiku, sklizne u travu). Posle toga se vraća po dve žute latice na sat, gospodin se vraća u podne; ako ga niko ne oduva do 01:00, vetar odnese seme. Dole je livada maslačaka, siva do podne, žuta posle podne. PL lista je bez okvira, produktivnost je crno-bela traka |
| My Passion | Iced Americano: slojevi tamnih braon nijansi, cifre i tekst kao led sa belim sjajem; na 80%+ u traci produktivnosti piše "How is possible?". Zvuci: Play je pucanj iz revolvera, PL para iz aparata za espresso, Pauza "cing cing" o keramičku šolju, Stop zveckanje leda |
| Jaje | lampa: sivo i tamno sivo dok tajmer stoji, a krem i belo (svetlo upaljeno) samo dok radiš; traka produktivnosti sija sve jače kako se puni |

Svaki skin ima svoje zvučne efekte za start, pauzu, stop, klik i podsetnik: Matrix digitalne pištaljke, Pastel mehuriće, Orah kucanje u drvo, Samuraj zvuk mača (izvlačenje, zamah, zvek), Mačkasti mjaukanje, Setsuna sočne "citrus" tonove, Mondrian obične čiste tonove, Jaje "plop" kao kad jaje ili oblutak padne u vodu, Maslačak vetar i šuštanje trave, My Passion kafu (vidi gore). Zvuci se prave u kodu (`timetracker/sounds.py`), nema audio fajlova. Isključuju se u meniju: **Zvučni efekti**. Podsetnik za neaktivnost i tada pusti sistemski zvuk.

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

Desni klik bilo gde (ili dugmence gore levo) otvara meni: skin, zvuci, produktivni sajtovi i programi, podsetnik za neaktivnost, uvek na vrhu, ažuriranje, mini traka, pokretanje sa Windows-om, izvoz, folder sa podacima, izlaz.

`Ctrl+Space` pali i pauzira tajmer.

**Podsetnik za neaktivnost:** ako tajmer radi, a ti 5 minuta ne dirneš tastaturu ni miš, odmah iskoči prozor (uvek na vrhu, sa zvukom) koji broji koliko te nema. Kad se vratiš, prozor zamrzne to vreme i pita: **Odbaci** (tajmer nastavlja bez tog vremena), **Odbaci i stani** ili **Zadrži**. Isto važi i posle zatvaranja laptopa. Granica (5, 10, 15, 30 min ili isključeno) se menja u meniju.

**Tray i mini traka:** zatvaranje prozora sklanja aplikaciju pored sata; tajmer radi dalje. Umanjenje (dugme _) je pretvara u poluprovidnu mini traku dole desno iznad taskbara, sa vremenom, zadatkom i ▶/❚❚; prelazak mišem je čini potpuno vidljivom, klik vraća pun prozor (isključuje se u meniju). Izlaz je u meniju.

**Produktivnost:** dok si aktivan za laptopom (sa ili bez tajmera), aplikacija gleda koji je program ili sajt u prvom planu i svrstava ga u produktivno, ometanje ili ostalo. Ispod PL liste stoji jedan red: *Produktivno 67% · ometanje 16%* sa trakom; klik na njega otvara pregled po programima i sajtovima za taj dan.

- Produktivno: Google Docs / Sheets / Slides, Word, Excel, PowerPoint, OneNote, LibreOffice, Notion, Obsidian, Overleaf.
- Ometanje: YouTube, Facebook, Messenger, Instagram, TikTok, Netflix, Reddit, X/Twitter i prodavnice (Amazon, eBay, AliExpress, Temu, Shein, Zalando, Etsy, KupujemProdajem, Ananas, Gigatron, WinWin i stranice sa "shop" ili "korpa" u naslovu).
- Sve ostalo je "ostalo". Svoje dodaješ u meniju **Produktivni sajtovi i programi...**: po jedna reč u redu, deo naslova ili sajt (`figma`, `canva.com`) ili program (`blender.exe`). Ispod je lista programa koji su danas bili u "ostalo"; izabereš jedan i klikneš **→ Produktivno** ili **→ Ometanje**. Važi odmah, a današnje vreme tog programa se odmah prebaci.
- Čuva se samo kategorija i kratak naziv (npr. "YouTube", "Word"), **nikad naslov prozora**. Vreme dok si neaktivan ili je ekran zaključan se ne broji.

## Na telefonu

Postoji i web verzija za telefon (folder `web/`): isti izgled, svi skinovi i zvuci (bez pokazatelja produktivnosti), lista unosa, CSV izvoz. Radi i bez interneta.

**Adresa:** https://ratkomilin.github.io/Personal-Time-Tracker/

- **iPhone (Safari):** otvori adresu → dugme Deli (kvadrat sa strelicom) → **Add to Home Screen**.
- **Android (Chrome):** otvori adresu → meni ⋮ → **Install app** ili **Add to Home screen**.

Posle toga se otvara kao obična aplikacija, preko celog ekrana.

Podaci na telefonu su **odvojeni** od laptopa i čuvaju se samo u tom telefonu. Rezervnu kopiju pravi meni ☰ → Rezervna kopija → Sačuvaj; tu je i CSV izvoz (i za "Sve"). Na telefonu nema podsetnika za neaktivnost, jer telefon ne dozvoljava aplikaciji da prati da li ga koristiš dok je u pozadini. Tajmer i dalje ispravno računa vreme kad zatvoriš aplikaciju ili zaključaš ekran.

Objava na tu adresu ide automatski (GitHub Actions, "Mobile web app") posle svake izmene u `web/` na grani main. Jednom treba uključiti: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Na e-ink telefonu (Mudita Kompakt)

Android aplikacija `TimeTracker-Kompakt.apk` nosi istu web verziju u sebi, ali u **E-ink** skinu: crno na belom, krupna slova, bez animacija i treptanja, a tajmer pokazuje sate i minute, pa se ekran osvežava jednom u minuti umesto svake sekunde (manje "duhova" i manja potrošnja baterije). Zvuci su podrazumevano isključeni. Ne treba joj internet.

Na Kompakt-u postoji samo E-ink skin (izbor skinova je sakriven).

Instalacija:
1. Preuzmi `TimeTracker-Kompakt.apk` sa stranice **Releases** (ili iz **Actions → Test and build → Artifacts → TimeTracker-android**).
2. Na računaru otvori **Mudita Center** (3.1.0 ili noviji) i poveži Kompakt kablom.
3. **Manage Files → App Installers → Add App Files** i izaberi APK, pa ga na telefonu instaliraj.

CSV izvoz i rezervna kopija se čuvaju u folder **Download** na telefonu. Nova verzija APK-a se instalira preko stare i podaci ostaju (sve verzije su potpisane istim ključem, `android/ptt-sideload.jks`, koji služi samo za ovu ličnu aplikaciju).

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

**Samoažuriranje:** exe sa stranice Releases na pokretanju (posle 30 s) i na svakih 6 sati proveri ima li novije izdanje. Ako ima, preuzme ga, proveri SHA-256 otisak, zameni sebe i ponovo se pokrene (umanjen); tajmer nastavlja jer je zapisan u bazi. Ako je otvoren neki dijalog, sačeka. Isključuje se u meniju (**Automatsko ažuriranje**), a **Proveri ažuriranje** proverava odmah. Exe iz Actions artifakta i pokretanje iz koda se ne ažuriraju sami. Web verzija na telefonu se osvežava sama (novi fajlovi stižu pri sledećem otvaranju); APK za Kompakt Android ne dozvoljava da se tiho zameni, novu verziju instaliraš preko Mudita Center-a.

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
| `timetracker/productivity.py` | pravila produktivno / ometanje i dnevni zbirovi |
| `timetracker/sounds.py` | sintetizovani zvučni efekti po skinu |
| `timetracker/updater.py` | samoažuriranje exe-a sa GitHub Releases |
| `timetracker/ui/skin.py` | teme i iscrtani elementi: paneli, dugmad, LCD cifre, analogni sat |
| `timetracker/ui/player.py` | glavni prozor i plejlista |
| `timetracker/ui/dialogs.py` | izmena unosa i podsetnik za neaktivnost |
| `web/` | mobilna web verzija (HTML/CSS/JS, bez biblioteka), testovi u `tests/test_web.py` |
| `android/` | Android aplikacija (WebView sa `web/` u sebi) za Mudita Kompakt; gradi je GitHub Actions |
