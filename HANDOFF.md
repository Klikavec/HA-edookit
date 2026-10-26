# Handoff – HA Edookit fork

## Aktuální stav
Fork 0.3.0: centrální obnova, soukromá cache, MQTT školní přehled, opravené rozpoznání dokončených úkolů a volitelné explicitní školní akce. Samostatná PC karta v edookit-school-card; integrace ji neobsluhuje. Žádná osobní školní data v repozitáři.

## Naposledy dokončeno
- [CX] 2026-10-26 – 66 regresních HA testů na 2026.10.3, lint a soukromý živý test prošly. Dokončení jednoho úkolu používá čerstvý formulář a potvrzení; detaily zpráv se otevírají pouze explicitní službou.

## Příští priority
1. Vydání 0.3.0 ověřeno po nasazení přes HACS a restartu HA2026.10.3. Karta samostatně nasazena včetně kontrastu pro světlé téma.
2. Dlouhodobé ověření změn HTML a session.

## Kontext pro druhého agenta
- MIT licence a autorství zachovány. Aktuální chování viz docs/school-panel.md.
- allow_school_actions je výchozí false; uživatel může zapnout dokončení vybraného úkolu a čtení zprávy. Automatické čtení detailů zůstává zakázané.
- Vícežákové neověřené seznamy mají stav unverified_student. Privátní data a screenshoty jsou mimo repozitář.
