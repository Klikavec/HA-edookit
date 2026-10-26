# Handoff – HA Edookit fork

## Aktuální stav
Fork 0.2.1: centrální obnova, soukromé uložení posledních dat, normalizovaný školní MQTT payload a opravené parsery vnořených seznamů. Bez osobních školních dat v repozitáři.

## Naposledy dokončeno
- [CX] 2026-10-26 – Implementace centrálního koordinátoru a kontraktu, 60 regresních testů prošlo; soukromý test s reálným rodičovským účtem také prošel.

## Příští priority
1. Nasazení přes HACS a ověření po restartu.
2. Dlouhodobé ověření obnovy session a změn portálu.

## Kontext pro druhého agenta
- Původní MIT licence a autorství zachovány. Nové chování viz docs/school-panel.md; původní README popisuje upstream.
- Žádné automatické čtení detailů zpráv. Vícežákové neověřené seznamy mají stav unverified_student.
- Osobní záznamy portálu, přístupy a skutečné vizuální důkazy jsou mimo repozitář.
