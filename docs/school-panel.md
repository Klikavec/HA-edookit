# Školní panel – fork 0.2.0

Tento fork vychází z joshuaaaaa/HA-edookit (MIT). Původní autorství a licence zůstávají zachovány. Kód alternativního projektu nebyl převzat.

## Chování tohoto forku

Jeden centrální asynchronní koordinátor řídí celý účet; původní koordinátory slouží entitám jako pohledy bez vlastních časovačů. Obnova probíhá po 45 minutách během vyučovacího dne do 16:00 a po třech hodinách mimo něj. Automatické obnovy se mezi 22:00 a 06:00 odkládají. První načtení bez uložených dat a ruční obnova mohou proběhnout i v noci. Europe/Prague a změny letního času jsou respektovány. Školní den vychází z reálného rozvrhu, nikoli z odhadovaného kalendáře prázdnin.

Při chybě jednotlivé oblasti zůstávají poslední data v privátní HA Store a označí se jako stará. Úspěšně potvrzený prázdný seznam se liší od neznámé struktury stránky. Nehotové úkoly po termínu zůstávají viditelné. Položky mají stabilní ID odvozené od portálového ID/URL a deduplikují se.

Příští týden se neprojektuje. Stav `available` vzniká jen z položek se skutečnými daty tohoto týdne. Pokud portál nevrátí potvrzený rozvrh, týden má stav `unavailable`.

Integrace automaticky neotevírá detaily zpráv, anket ani úkolů. Tím se vyhne označení zpráv jako přečtených. Senzor textu zprávy obsahuje pouze dostupný náhled. Neoznačuje úkoly jako hotové a neodesílá omluvenky ani jiné změny školních záznamů. Navigace rozvrhu může měnit filtr ve vlastní HTTP session, kterou nesdílí s běžným prohlížečem.

U rodinného účtu s více dětmi se neověřené společné úkoly a písemky do jednotlivých dětských přehledů neposílají; stav je `unverified_student`. Je nutné ověřit přepínání žáka či explicitní identifikátory v datech. Jeden žák na účtu tento problém nemá.

## HA entity a MQTT

Původní entity zůstávají. Přibývá senzor **Školní přehled**, jehož atributy tvoří normalizovaný payload níže. Velké seznamy tohoto senzoru se neukládají do historie recorderu. Přesné entity ID generuje HA podle názvu žáka a jazyka.

V možnostech integrace lze nastavit:
- `school_student_id`: portálové ID vybraného žáka; prázdný řetězec pro účet s jediným žákem.
- `school_mqtt_topic`: vlastní topic končící `/school/set`, například `yoga_panel/PANEL_ID/school/set`. Prázdné pole publikování vypíná.

MQTT používá QoS 1 a retain. Obnovený panel po restartu obdrží poslední payload. Panel navíc uchovává svou lokální kopii a po restartu ji označí jako starou. Starý `dashboard/set` kontrakt ani domácí automatizace se nemění. Při chybě MQTT zůstávají data dostupná v HA; další pravidelná či ruční obnova publikování zopakuje.

```json
{
  "schema_version": 1,
  "student_id": "",
  "timezone": "Europe/Prague",
  "timetable": {"days": [], "bell": [], "weeks": []},
  "homework": [],
  "exams": [],
  "last_updated": null,
  "published_at": "2026-01-01T12:00:00+01:00",
  "sync_status": "loading",
  "sections": {"timetable": "unknown", "homework": "unknown", "exams": "unknown"}
}
```

Tento příklad je syntetický. `days` obsahuje datum a seznam `lessons`; bloky uchovávají předmět, zkratku, hodinu, časy, místnost, učitele, poznámku, učivo, písemku, změnu, zrušení a případný rozsah události. `bell` definuje sloupce. `weeks` obsahuje `start` a `status`. Úkoly/písemky mají `id`, `subject`, `title`, `description`, `due` či `date`, dostupné datum zadání a odkaz. Časy bez offsetu v portálových položkách jsou místní v uvedeném časovém pásmu.

Panel musí používat `textContent`, nerozbalovat školní obsah jako HTML, validovat verzi a rozměry payloadu a rozlišovat chybu od prázdného seznamu. Topic obsahuje osobní školní údaje; přístup k brokeru a HA zálohám musí zůstat soukromý.

## Instalace, aktualizace a rollback

1. Před změnami vytvořit zálohu Home Assistanta a dotčeného panelu. Nainstalovat pouze jednu integraci domény `edookit`.
2. V HACS přidat `Klikavec/HA-edookit` jako integraci a instalovat otestovanou verzi. Restartovat HA v dohodnutém čase.
3. Přidat Edookit a zadat rodičovský Plus4U účet přímo v HA. Heslo a cookies nikdy neposílat na GitHub. Google login tento klient nepodporuje. CAPTCHA ani 2FA se neobcházejí.
4. Ověřit jméno žáka, aktuální i další týden, úkoly a písemky proti portálu. Teprve potom nastavit MQTT topic pro konkrétního žáka.
5. Aktualizace provádět po záloze a testech; zkontrolovat ruční obnovu a stavy synchronizace. Po změně HTML portálu opravit parser podle soukromého záznamu, do testů vložit pouze syntetický či skutečně anonymizovaný vzorek.
6. Rollback: vypnout MQTT topic v možnostech, obnovit předchozí verzi komponenty/zálohu HA a restartovat. Panel vrátit z vlastní zálohy. Při úplném odinstalování vymazat retained zprávu pouze na příslušném `school/set` topicu, aby nezůstala stará školní data. Nedotýkat se `dashboard/set` ani ostatních domácích topics.

Ruční refresh funguje tlačítkem integrace nebo službou `edookit.refresh`. Kvůli centrální konzistenci načítá celý účet; starší parametr `what` zůstává přijímán pro kompatibilitu. Starší nastavení denního rozvrhu/chytrého časovače už neřídí obnovu tohoto forku.

## Testy a omezení

`pytest`, `ruff check custom_components tests`, `ruff format --check custom_components tests`. Testy používají syntetické fixtures. Ověřují parsování vnořených portálových seznamů, stabilní ID, prázdné seznamy versus chyby, uchování nehotových úkolů, obnovení po reloadu, noční klid, ruční obnovu, změny rozvrhu a DST. Skutečná funkčnost konkrétního účtu, restart HA a fyzické zobrazení panelu se musí ověřit zvlášť.

Portál může změnit HTML. Při zcela prázdném rozvrhu bez rozeznatelné události zůstane stav neověřený; integrace nesmí vymyslet školní volno ani potvrzený příští týden. Při více žácích je přiřazení úkolů omezené, jak je uvedeno výše. Sekundární moduly závisejí na škole a musí se ověřit samostatně.
