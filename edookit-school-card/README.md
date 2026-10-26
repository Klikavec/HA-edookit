# Školní přehled pro Home Assistant

Samostatná Lovelace karta používá stejný renderer jako Lenovo panel. Neinstaluje se jako součást integrace.

Zkopírujte `edookit-school-card.js`, `school.js` a `school.css` do `/config/www/ciri-school/`. Přidejte modul `/local/ciri-school/edookit-school-card.js` do zdrojů Lovelace. Na dashboardu s pohledem typu panel použijte:

```yaml
type: custom:edookit-school-card
entity: sensor.edookit_priklad_skolni_prehled
title: Škola
```

Akce Splněno/Přečteno jsou dostupné pouze při explicitním povolení v možnostech integrace. Odesílají jen ID položky do omezené HA služby. Žádné přístupy k Edookitu nejsou součástí karty.
