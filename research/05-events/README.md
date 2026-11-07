# 05 – Big events in Luxembourg City, for map event layers

Reference material for the "event changes to the map" feature (ROADMAP, The map #2): on the dates of big events the map gets an extra overlay. The base art has no people, vehicles or decorations, so every event layer adds its own stalls, rides, stages, flags, lights, fireworks and crowds on top.

How to use this folder:
- `events.json`: one record per event for the map code: `id, name, name_local, rule, dates_2026, dates_2027, locations [{name, lat, lon}], visual_impact, layer_idea, website`. Each date object has `start`, `end` and a `status`: **confirmed** (published by the organiser or city), **computed** (worked out from the rule, not yet published) or **fixed date**. Coordinates are approximate centre points (WGS84), good enough to place a layer, not to draw outlines. Take outlines from OpenStreetMap.
- `images/`: **51** freely licensed photos (Wikimedia Commons), named `<event>__<what>.jpg`, downloaded as 1600 px thumbnails.
- `sources.json`: one record per image: `file, event, shows, source_page, author, licence, licence_url, date, original_size`. Almost all are CC BY-SA or CC BY, so attribution is needed if they are published. Two are public domain and one is CC0.
- Dates were checked on 6 Nov 2026. Most 2026 events have already happened, so their dates are confirmed by the programmes and the reports afterwards. Almost nothing for 2027 is published yet.

Visual impact: **HIGH** means the event changes how whole squares or districts look for days or weeks: Winterlights, Schueberfouer and National Day. **MEDIUM** means a visible but local or one-day change. **LOW** means little shows from above.

## Contents
[Calendar](#calendar) · [Winterlights](#winterlights) · [New Year's Eve](#nye) · [Schueberfouer](#fouer) · [National Day](#nationalday) · [Octave](#octave) · [Éimaischen](#emaischen) · [Buergbrennen](#buergbrennen) · [Carnival](#carnival) · [Summer events](#summer) · [Autumn events](#autumn) · [Discontinued festivals](#discontinued) · [One-off and historic events](#historic) · [Layout plans](#plans) · [Images](#images) · [Top 5](#top5) · [Sources](#sources)

<a id="calendar"></a>
## Year calendar

| Month | Event | Rule | 2026 | 2027 | Impact |
|---|---|---|---|---|---|
| Jan | Winterlights (end) | first Sunday of January | until 3 Jan 2027 ✔ | until 2 Jan 2028 (c) | HIGH |
| Feb | Carnival / Fuesent (Diekirch cavalcade) | Carnival Sunday (Easter −49) | 15 Feb ✔ | 7 Feb (c) | low (outside the city) |
| Feb | Buergbrennen | first Sunday of Lent (Easter −42), some on the Saturday before | 21–22 Feb ✔ | 13–14 Feb (c) | medium |
| Mar | Pétange cavalcade | mid-Lent Sunday (Laetare, Easter −21) | 15 Mar (c) | 7 Mar (c) | low (outside the city) |
| Mar/Apr | Éimaischen | Easter Monday | 6 Apr ✔ | 29 Mar (c) | medium |
| Apr–May | Octave and Mäertchen | Saturday before the 3rd Sunday after Easter to the 5th Sunday after Easter | 25 Apr – 10 May ✔ | 17 Apr – 2 May (c) | medium |
| May | ING Night Marathon | a Saturday evening in May | 16 May ✔ | not published | medium |
| Jun–Sep | Summer in the City (umbrella) | mid-June to mid-Sept | 12 Jun – 18 Sep ✔ | (c) | low |
| Jun | Fête de la Musique (city) | weekend before 21 June | 12–14 Jun ✔ | 11–13 Jun (c, guess) | medium |
| Jun | **National Day eve** + National Day | 22 + 23 June | Mon 22 + Tue 23 Jun ✔ | Tue 22 + Wed 23 Jun (fixed) | HIGH |
| Jul | Kinnekswiss loves... | first weekend of July | 3–5 Jul ✔ | 2–4 Jul (c) | medium |
| Jul | Luxembourg Pride (city years) | first half of July; city and Esch alternate | week 4–12 Jul, Street Fest 10–11 Jul ✔ | probably Esch (c) | medium |
| Jul | Blues'n Jazz Rallye | a Saturday in mid/late July | 18 Jul ✔ | 17 Jul (c, guess) | medium |
| Jul–Aug | City Open Air Cinema | late July (Knuedler), early Aug (Bonnevoie) | 23–28 Jul, 6–8 Aug ✔ | (c) | low |
| Aug–Sep | **Schueberfouer** | Friday between 20 and 26 Aug, 20 days | 21 Aug – 9 Sep ✔ | 20 Aug – 8 Sep (c) | HIGH |
| Sep | Liberation anniversary | 10 September | 10 Sep | 10 Sep | low |
| Sep | Tour de Luxembourg | mid-September, 5 stages | 16–20 Sep ✔ | not published | low |
| Oct | Nuit des Musées | a Saturday in October (2nd Sat. in 2025/26) | 10 Oct ✔ | 9 Oct (c) | low |
| Oct | Halloween | 31 Oct; city events the weekend before | 24–25 Oct (neimënster) ✔, 31 Oct | 23–24 Oct (c), 31 Oct | low |
| Nov | All Saints (Allerhellgen) | 1 November | Sun 1 Nov | Mon 1 Nov | low |
| Nov–Jan | **Winterlights** (Christmas markets) | Friday 9 days before the 1st Sunday of Advent to the first Sunday of January | 20 Nov 2026 – 3 Jan 2027 ✔ | 19 Nov 2027 – 2 Jan 2028 (c) | HIGH |
| Dec | New Year's Eve | 31 December | 31 Dec | 31 Dec | medium |

✔ = confirmed by an official or organiser source. (c) = computed from the rule, not yet published. Moveable feasts: Easter is 5 Apr 2026 and 28 Mar 2027; the 1st Sunday of Advent is 29 Nov 2026 and 28 Nov 2027.

---

<a id="winterlights"></a>
## Winterlights – Christmas markets ★ HIGH
**Names:** Winterlights; Lëtzebuerger Chrëschtmaart (Place d'Armes), Wantermaart (Place de la Constitution), Niklosmaart (Place de Paris), Wanterpark (Kinnekswiss) (lb); marchés de Noël (fr).

**When.** Opens on the Friday nine days before the 1st Sunday of Advent (the Friday before Christ the King Sunday) and closes on the first Sunday of January. 2025: 21 Nov 2025 – 4 Jan 2026. **2026: 20 Nov 2026 – 3 Jan 2027, confirmed** on the city's Winterlights page. 2027: 19 Nov 2027 – 2 Jan 2028 (computed). About 6.5 weeks; opening days and hours vary per market.

**Where and what it looks like.** This is the 2025 layout (Chronicle.lu, 2025 preview). The city has not published the 2026 layout yet; the main squares do not change from year to year.

| Site | Coordinates | Contents (2025) |
|---|---|---|
| Place d'Armes – Lëtzebuerger Chrëschtmaart (here since 1984) | 49.6111, 6.1301 | 38 wooden chalets around the bandstand, 12 m decorated tree, nativity scene |
| Place de la Constitution – Wantermaart | 49.6095, 6.1292 | 40 chalets, **32 m big wheel**, giant Christmas pyramid, rides, panoramic dining, all on the bastion beside the Gëlle Fra above the Pétrusse valley |
| Place de Paris (Gare) – Niklosmaart | 49.6031, 6.1332 | 14 chalets |
| Kinnekswiss (municipal park) – Wanterpark | 49.6127, 6.1253 | open-air ice rink, food village, DJ sets |
| Place Émile Hamilius – Sapin Royal (new in 2025) | 49.6119, 6.1275 | 10 m tree, Christmas train, 6 chalets |
| Place Guillaume II (Knuedler) – Winterkids, Adventskalennerhaus | 49.6106, 6.1322 | giant slide, flying-reindeer carousel, children's village; the Hôtel de Ville lit as an Advent calendar |

The prompt also listed the **Rives de Clausen**. No current official source names it as a Winterlights market, so it has been left out of the JSON. Light garlands also hang over Grand-Rue, rue Philippe II, avenue de la Gare and the shopping streets, and there are illuminated trees, including the blue "light tree" on the Knuedler in 2017. On 30 Nov 2025 St Nicholas toured the city by tram (Kleeschen on Tour).

Colours: dark-brown chalets with white or snow-coloured roofs, warm-white fairy lights, red and gold decorations, a multicoloured LED wheel, a blue-lit ice rink.

**Visitors:** not published per edition. The tourist office treats it as the biggest winter draw.

**History.** The Christmas market on Place d'Armes dates from 1984. The city later grouped the markets, lights, ice rink and children's programme under the Winterlights name. The big wheel next to the Gëlle Fra is now its landmark, and photos of it with the memorial are the classic Christmas view of the city.

**Website:** <https://www.vdl.lu/en/visiting/leisure-and-recreation/festivals-fairs-and-events/winterlights-0> · <https://www.luxembourg-city.com/en/winterlights>

**Map layer idea.** Chalet rings on Place d'Armes and Place de la Constitution, the wheel and pyramid on the Constitution bastion (it shows from far away, so use it as the layer's icon), a smaller chalet group on Place de Paris, the tree and train on Hamilius, an oval ice rink on the Kinnekswiss lawn, and the slide and carousel on the Knuedler. Add string lights along the old-town streets. At night, the warm glow of the chalets should be the brightest thing in Ville Haute. It combines well with a snow or winter-trees season layer.

Images: `winterlights__wantermaart-2025-a.jpg` and `-b.jpg` (the market and wheel seen from above the bastion: the best layout reference), `winterlights__constitution-overview-2015.jpg`, `winterlights__wantermaart-gelle-fra-big-wheel.jpg`, `winterlights__wantermaart-night.jpg`, `winterlights__wantermaart-2017.jpg` (pyramid), `winterlights__place-darmes-panorama-2024.jpg`, `winterlights__place-darmes-chalets-2024.jpg`, `winterlights__niklosmaart-place-de-paris-2024.jpg`, `winterlights__hotel-de-ville-lights-2017.jpg`, `winterlights__place-guillaume-blue-tree-2017.jpg`.

<a id="nye"></a>
## New Year's Eve – MEDIUM
**Names:** Silvester (lb), Saint-Sylvestre (fr). **When:** 31 Dec, every year.

**What.** The Christmas markets are still up (Winterlights runs into January), and the bars and restaurants in the old town and Grund fill up. No official city fireworks display was found. In 2025 **Luxembourg City banned private fireworks** in its territory (as did Esch, Differdange, Dudelange, Vianden and Wiltz, per Chronicle.lu). The midnight sky over the city is therefore quieter than in neighbouring countries: bursts come mostly from the surrounding communes.

**Map layer idea:** reuse the Winterlights layer with a night sky, add a few small firework bursts on the horizon (surrounding communes), and maybe a midnight countdown easter egg. Image: `fireworks__over-city-night-2018.jpg` (CC0, fireworks over the city at night; the occasion is not stated).

<a id="fouer"></a>
## Schueberfouer ★ HIGH
**Names:** Schueberfouer (lb), Schobermesse (de), "d'Fouer". The opening walk is the **Hämmelsmarsch** ("wether march").

**When.** It opens on the Friday that falls between 20 and 26 August and runs 20 days to the Wednesday three weeks later (2023: 25 Aug–13 Sep, 2024: 23 Aug–11 Sep, 2025: 22 Aug–10 Sep). **2026: Fri 21 Aug – Wed 9 Sep, confirmed** (city programme, Chronicle). Official opening at 17:00 on 21 Aug with a ribbon-cutting by the mayor. **Hämmelsmarsch on Sat 22 Aug.** Fouersonndeg on 30 Aug, braderie on Mon 7 Sep, half-price last day and **closing fireworks at 22:00 on 9 Sep from the Pont Grande-Duchesse Charlotte (Red Bridge)**. **2027: 20 Aug – 8 Sep (computed)**; the city has confirmed a 2027 edition (poster competition for 2026–2028) but not its dates. Open daily 12:00–01:00, food from 11:00.

**Where.** Champ du Glacis, Limpertsberg (centre about 49.6187, 6.1243): the large open car park between avenue de la Faïencerie, allée Scheffer, rue des Glacis and avenue Pasteur, right next to the Glacis tram stop. The fair covers 4.44 ha with seven public entrances. The layout has stayed the same since 2017, when the site was redesigned around the new tram line. **Restaurants and the big food halls are grouped in the north-west part of the Glacis**, and the rides, attractions and stalls fill the rest. Camelots (market traders) line allée Scheffer along the edge (photo `schueberfouer__allee-scheffer-stalls.jpg`).

**What it looks like.** In 2026: 214 establishments from five countries. The city's breakdown lists nine flat rides, eight elevated rides, two rail-guided rides, nineteen children's rides, ghost trains, walk-throughs, 11 restaurants, 42 savoury and 18 sweet take-away stands, and 15 confectionery stands. New in 2026: *Dr Archibald – Master of Time*, *Wilde Maus*, *Meltdown*, *Skater*. Famous regulars and photo motifs include the **big wheel** (the fair's landmark; it has been a different travelling wheel in different years), Bayern Kurve, chair-o-planes, the "Big Splash" and Wildwasser log flumes, drop towers ("Power Tower", "Take Off"), "Infinity" and ghost trains. By day it is a dense patchwork of coloured canopies, white tents and steel rides on grey asphalt. **By night it is the brightest place in the city**, with neon, LED-chased fronts and the wheel lit in changing colours. Food motifs: Gromperekichelcher (potato fritters), fried Moselle fish, Paangecher, Bretzels, beer halls.

**Hämmelsmarsch.** Shepherds in blue smocks lead a few sheep with ribbons, followed by a brass band playing the Hämmelsmarsch tune, through the streets of the old town and the cafés, collecting money. The fair's mascot "Lämmy" is a sheep, and there is a Hämmelsmarsch fountain on Grand-Rue (Puits-Rouge).

**Visitors:** about **2 million** a year (city organiser's average).

**History.** Founded in **1340 by John the Blind**, Count of Luxembourg and King of Bohemia, as a merchants' fair around St Bartholomew's day (24 August). Over the centuries it became a funfair, and big rides arrived in the early 20th century. It is held on the Glacis, the open ground once left clear in front of the fortress, and the 2026 edition was the 684th (sources count differently).

**Website:** <https://fouer.vdl.lu> (redirects to the city's Schueberfouer page)

**Map layer idea.** Fill the Glacis polygon with a dense, colourful grid of ride sprites: the big wheel as the tallest object and the layer's icon, a coaster, a drop tower, chair-o-planes, a log flume with splashing water, and many small canopies and stalls in between. Put the food halls (long tents with beer-garden benches) in the north-west corner and a row of stalls along allée Scheffer. Animate the wheel and the rides, and give the night layer the strongest glow in the city. On 9 Sep, add the closing fireworks over the Alzette valley from the Red Bridge. On the opening weekend, a tiny Hämmelsmarsch sprite (sheep and band) can walk through the old town as an easter egg. Outside fair time the Glacis is an empty car park (photo `schueberfouer__glacis-empty-aerial.jpg`).

Images: `schueberfouer__overview-from-big-wheel-2013.jpg` (the fair from above), `schueberfouer__night-overview.jpg`, `schueberfouer__big-wheel-night.jpg`, `schueberfouer__rides-2018.jpg`, `schueberfouer__chair-o-planes.jpg`, `schueberfouer__log-flume-big-splash.jpg`, `schueberfouer__food-stall-gromperekichelcher.jpg`, `schueberfouer__stall-alley-night-2013.jpg`, `schueberfouer__allee-scheffer-stalls.jpg`, `schueberfouer__closing-fireworks.jpg`, `schueberfouer__haemmelsmarsch-2019.jpg`, `schueberfouer__haemmelsmarsch-sheep-2015.jpg`, `schueberfouer__glacis-empty-aerial.jpg`.

<a id="nationalday"></a>
## National Day (Grand Duke's official birthday) ★ HIGH
**Names:** Nationalfeierdag, Groussherzogsgebuertsdag (lb); Fête nationale (fr). The eve is the "Virowend".

**When.** 23 June every year (public holiday). The big city party is on **the eve, 22 June**. 2026: Mon 22 + Tue 23 June, **confirmed**. It was Grand Duke Guillaume's first National Day as sovereign. 2027: Tue 22 + Wed 23 June (fixed; programme not yet published).

**Programme and places (2026, government and city).**

| Time | What | Where |
|---|---|---|
| 22 Jun 16:00 | Changing of the guard | Grand Ducal Palace (49.6106, 6.1338) |
| 22 Jun 19:45 | Folklore, then a DJ from 22:00 to 01:30 | Place d'Armes |
| 22 Jun 20:30–02:30 | "City Sounds" open-air concert (Alesso, Nicky Romero …), gates 17:00 | Champ du Glacis |
| 22 Jun 21:30 | **Torchlight procession** (Fakelzuch), about 2,800 marchers (fire brigade, sports and music clubs, scouts) | Place du Théâtre → Côte d'Eich → rue du Fossé → Place Guillaume II → Place Clairefontaine |
| 22 Jun 21:30 | Grand Ducal couple received by the mayor | Place Guillaume II (Hôtel de Ville) |
| 22 Jun 23:00 | **Fireworks, about 17 min, set to music, launched from the Pont Adolphe** | Pétrusse valley, seen from the bridges and the boulevards |
| 23 Jun 10:00 | Official ceremony | Philharmonie, Kirchberg |
| 23 Jun 10:00–18:00 | "Spillfest" family play festival | Kinnekswiss |
| 23 Jun 11:00 | 21-gun salute | Fetschenhof (Cents) |
| 23 Jun 12:00 | **Military parade** (army, a French Army detachment, police, customs, CGDIS, Red Cross, bands) with a flypast (A400M, A330 tanker, police helicopter) | Avenue de la Liberté (Gare) |
| 23 Jun 16:30 | Te Deum | Notre-Dame Cathedral |
| 23 Jun 17:30 | Concert (headliner OneRepublic) | Champ du Glacis |

**What it looks like.** **Flags everywhere**: the red-white-light-blue national flag (and in some years the royal monogram flag) on poles along the boulevards and Pont Adolphe, on public buildings and across Grand-Rue. Decorated city buses carry flowers for the procession. On the eve there are crowds on all the old-town squares, torches snaking through the streets at night, and the fireworks over the Pétrusse gorge, the most photographed moment. The next morning there are grandstands, barriers, military vehicles and marching blocks on avenue de la Liberté.

**Visitors:** up to **30,000** expected on the eve (the city's figure; this is the capacity limit of the event zone).

**History.** Luxembourg celebrates its sovereign's birthday as the national day. Since 1961 it has been held on 23 June rather than on the real birthday (Grand Duchess Charlotte's was in January), for better weather. The date was kept for Jean, Henri and now Guillaume.

**Website:** <https://monarchie.lu> · <https://gouvernement.lu> (programme press release) · <https://www.vdl.lu>

**Map layer idea.** A day layer for 23 June: flags along the boulevards, avenue de la Liberté and Pont Adolphe; parade blocks and vehicles on avenue de la Liberté with grandstands; a plane silhouette crossing the map. A night layer for 22 June: a torch line along the procession route, crowds on the Knuedler, Place d'Armes and Place Clairefontaine, a lit stage on the Glacis, and a **big firework display over the Pétrusse valley at Pont Adolphe** (animated bursts in red, white and blue). The fireworks are the most "isometric-friendly" moment of the year.

Images: `national-day__flags-2023.jpg` (flags along the Pétrusse with Pont Adolphe), `national-day__flags-grand-rue.jpg`, `national-day__military-parade-2016.jpg`, `national-day__flypast-2019.jpg`, `national-day__torchlight-decorated-bus-2016.jpg`, `national-day__clairefontaine-preparations-2016.jpg`. **No freely licensed photo of the National Day fireworks over the Pétrusse was found on Commons.** `fireworks__over-city-night-2018.jpg` is a generic stand-in. Non-free examples: Paperjam's "how Luxembourg celebrates National Day" article (photo by Nader Ghavami) and Chronicle.lu galleries (links below).

<a id="octave"></a>
## Octave of Our Lady of Consolation (Oktav) and the Mäertchen – MEDIUM
**Names:** Muttergottesoktav, Oktav; Oktavmäertchen or Mäertchen (lb); Octave de Notre-Dame (fr).

**When.** From the Saturday before the 3rd Sunday after Easter to the 5th Sunday after Easter (Easter +20 to Easter +35 days); the **closing procession is on the final Sunday**. 2025: 10–25 May. **2026: 25 Apr – 10 May, confirmed** (cathol.lu programme; the Grand Ducal couple attended the closing on 10 May). 2027: **17 Apr – 2 May (computed)**. In 2025 the closing procession started at 15:00 from the cathedral.

**Where.** Notre-Dame Cathedral (49.6097, 6.1316) for the pilgrim masses. The **Mäertchen market is on Place Guillaume II (Knuedler)**, open 11:00–22:00, with about 50 food stalls around a covered central terrace of more than 1,000 m², plus game stalls and small fairground rides. The weekly market moves to Place de la Constitution during it. In 2026 a temporary **71 m "Look 360 Panorama" observation tower** stood on Place de la Constitution (24 Apr – 14 Jun). The closing procession takes the statue of the Consolatrix Afflictorum through the old-town streets around the cathedral. The exact 2026 route was not published online; check the cathol.lu programme PDF.

**What it looks like.** Pilgrim groups with parish banners walking up to the cathedral; the cathedral portal decorated with flags and flowers; on the closing Sunday a long procession with clergy, the Grand Ducal family, uniformed groups and the decorated statue. Meanwhile the Knuedler becomes a small fair with a tent roof.

**Visitors:** not published; tens of thousands of pilgrims over the two weeks (estimate).

**History.** The pilgrimage to Our Lady, Comforter of the Afflicted (Consolatrix Afflictorum), began in the 1620s. She was declared patroness of the city in 1666 and of the country in 1678. The 2025 Octave was billed as the 400th. The Mäertchen grew up to feed the pilgrims.

**Website:** <https://www.cathol.lu> (programme PDFs: `Programme_OCTAVE_FR._2026_pdf.pdf`) · <https://www.vdl.lu>

**Map layer idea.** A tent-roofed food market with small stalls on the Knuedler, pilgrim flags at the cathedral, and on the closing Sunday a slow procession sprite with a canopy and statue circling the cathedral block. Optional: the tall panorama tower on Place de la Constitution in the 2026 version.

Images: `octave__closing-procession-engels-1893.jpg` (PD, 1893 drawing of the closing procession), `octave__cathedral-portal-2016.jpg` (portal decorated for the Octave), `octave__400-years-cathedral-mass.jpg` and `octave__400-years-statue.jpg` (Dec 2024 jubilee).

<a id="emaischen"></a>
## Éimaischen – MEDIUM
**Names:** Éimaischen, Eemaischen (lb), from Emmaus.

**When.** Easter Monday. **2026: 6 Apr, confirmed** (the 197th edition). **2027: 29 Mar (computed; the rule is fixed).** One day, 08:00–17:00.

**Where.** The **Marché-aux-Poissons (Fëschmaart)**, the oldest square of the city (49.6111, 6.1366), and the lanes in front of the National Museum of History and Art (MNHA). A smaller Éimaischen takes place in Nospelt (Kehlen), the potters' village.

**What it looks like.** In 2026: 22 stands selling **Péckvillercher** (painted clay bird whistles, sold only at the Éimaischen), 23 pottery stands, 22 craft stands, food and drink stalls, and music at the Fëschmaart and in front of the MNHA. There are thousands of visitors, children blowing the whistles, and pastel spring colours.

**History.** An Easter Monday market on the Fëschmaart, documented since the 19th century (the 197th edition in 2026 points to about 1829). The whistles come from the Nospelt pottery tradition. Each year a limited-edition whistle is made.

**Website:** <https://www.vdl.lu> (Éimaischen page) · <https://www.luxembourg-city.com/fr/agenda/event/eimaischen>

**Map layer idea.** Stalls filling the Fëschmaart, little coloured bird sprites on the tables, and tiny animated birds or notes as an easter egg (the whistle sound).

Images: `emaischen__market-2022.jpg`, `emaischen__peckvillercher-2022.jpg`.

<a id="buergbrennen"></a>
## Buergbrennen – MEDIUM (small area, strong at night)
**Names:** Buergbrennen, Buergsonndeg (lb); dimanche des Brandons, Fête des Brandons (fr).

**When.** First Sunday of Lent (Easter −42); some places hold theirs on the Saturday. **2026: 21–22 Feb, confirmed** (national listings). **2027: 13–14 Feb (computed).** In the evening, after dark.

**Where.** Bonfires are built by local youth or scout clubs in almost every commune. In Luxembourg City they are held in several quarters: photos from **Cents** (2006) and **Bonnevoie** (2019), and Paperjam describes a large one at the foot of the "Schlittenhiewel" in the **Pétrusse valley**. The 2026 city-quarter list was not found online.

**What it looks like.** A tall pile of wood and straw, often built round a pole with a **cross or "castle" (Buerg)** on top, burnt at dusk. There are big flames, sparks and smoke, a crowd round it, and mulled wine and soup stalls.

**History.** A pre-Christian spring fire to drive out winter. Remich burns and throws a straw man (Stréimännchen) into the Moselle.

**Map layer idea.** Two or three animated bonfires with a soft orange glow on open ground in the quarters (Pétrusse valley meadow, Cents, Bonnevoie), best on a night or dusk layer in February.

Images: `buergbrennen__bonnevoie-2019.jpg`, `buergbrennen__cents-2006.jpg`.

<a id="carnival"></a>
## Carnival (Fuesent) – LOW for the city
**Names:** Fuesent / Fuesend (lb), carnaval, cavalcade (fr).

**When.** The season runs to Ash Wednesday (18 Feb 2026; 10 Feb 2027). The main **cavalcades are outside the capital**: **Diekirch** on Carnival Sunday (58th cavalcade on **15 Feb 2026**, confirmed by Commons photos; 2027: 7 Feb, computed), **Pétange** at mid-Lent (Laetare Sunday: 15 Mar 2026 and 7 Mar 2027, computed and unconfirmed), and Esch-sur-Alzette, Schifflange and others. Luxembourg City itself has carnival balls and children's events, but no big street parade was found.

**What it looks like:** tractor-drawn floats, brass bands, masked groups, confetti.

**Map layer idea:** confetti and a few masked figures in the old town as a light easter egg, since the parades happen off the map.

Image: `carnival__diekirch-cavalcade-2026.jpg`.

<a id="summer"></a>
## Summer events

### Summer in the City (umbrella) – LOW
The tourist office's summer programme. **2026: 12 Jun – 18 Sep, confirmed** (31st edition; LCTO press release of 9 June 2026). It includes City Sounds on the Glacis (22–23 June), Kinnekswiss loves... (3–5 July), the Blues'n Jazz Rallye (18 July), the open-air cinema, guided tours of the Grand Ducal Palace (18 Jul–30 Aug), and it closes with the Schueberfouer. Website: <https://summerinthecity.lu>. **Layer idea:** café terraces and parasols on the old-town squares all summer, as a mild "summer" variant.

### Fête de la Musique – MEDIUM
The official day is 21 June. Luxembourg City held its programme on **12–14 June 2026 (confirmed)** with five stages: **Place Guillaume II, Place d'Armes, Place de la Constitution, Place Joseph Thorn and Place du Puits-Rouge**. Nationally there were about 300 free concerts, and Dudelange has its own big edition. 2027: probably 11–13 June (guess). **Layer idea:** small lit stages with crowds on the five squares. Image: `fete-de-la-musique__knuedler-2026.jpg` (orchestra stage on the Knuedler, 2026). Website: <https://www.vdl.lu/en/visiting/leisure-and-recreation/festivals-fairs-and-events/fete-de-la-musique>

### Kinnekswiss loves... (and MeYouZik) – MEDIUM
Free open-air concerts on the **Kinnekswiss**, the sloping lawn of the municipal park below the Villa Vauban and Hamilius (49.6127, 6.1253). **2026: 3–5 July, confirmed** (LCTO). 2025: 4–6 July. 2027: 2–4 July (computed). In past editions the Luxembourg Philharmonic gave a summer concert there. **Layer idea:** a big stage at the foot of the lawn and picnic crowds on the grass. The **Kinnekswiss** also hosts the Winterlights ice rink and the National Day Spillfest, so one Kinnekswiss "event slot" can serve several layers. *MeYouZik* (the World MeYouZik Festival) was a free world-music festival created in 2007 (European Capital of Culture year) on the old-town squares (Place Guillaume II, Place d'Armes, Place de la Constitution, rue du Saint-Esprit). No recent edition was found, so it is treated as historic.

### Blues'n Jazz Rallye – MEDIUM
**Saturday 18 July 2026 (confirmed)**, the 30th edition. More than 40 bands and brass bands from 16:00 in the valley quarters of **Grund, Clausen and Pfaffenthal**, on outdoor stages and in cafés; free. 2027: probably 17 July (guess, mid-July Saturday). **Layer idea:** the nicest summer-night layer for the valleys: stages on the Neimënster forecourt, Rives de Clausen and the Pfaffenthal squares, fairy lights across the lanes, crowds walking along the Alzette. Images: `blues-jazz-rallye__2023-a.jpg` (Pfaffenthal crowds with the viaduct), `blues-jazz-rallye__2023-b.jpg` (stage). Website: <https://summerinthecity.lu>

### City Open Air Cinema (Ville Haute open-air cinema) – LOW
The Cinémathèque's free screenings, 40th edition in 2026: **on the Knuedler (Place Guillaume II) 23–28 July 2026**, then **Place Léon XIII, Bonnevoie, 6–8 August 2026** (both confirmed). There is also the **Sunset Cinema in Parc Kirchberg** for about three weeks in summer (2026 listing from 29 July). **Layer idea:** a glowing screen and rows of chairs on the Knuedler at night. Website: <https://www.cinematheque.lu>

### Luxembourg Pride – MEDIUM (in city years)
Pride Week **4–12 July 2026** (official site; one outlet says 2–11). **Street Fest Fri 10 – Sat 11 July on Place Guillaume II (City Hall stage) and Place Clairefontaine (DJ stage)**, with the **Equality March** on Saturday afternoon (confirmed). The host city alternates between Luxembourg City and Esch-sur-Alzette, so 2027 is probably Esch (unconfirmed). **Layer idea:** rainbow flags on the Hôtel de Ville and lamp posts, two stages, a rainbow march line. Website: <https://www.luxembourgpride.lu>. No usable free crowd photo was found; the Commons Pride 2026 files are performer portraits.

### ING Night Marathon Luxembourg – MEDIUM
**Saturday 16 May 2026, start 19:00, confirmed** (19th edition, about 18,000 participants, a record). 2027 not published (a Saturday in May, avoiding Whitsun). Start and finish are at **Luxexpo The Box, Kirchberg**. The route crosses the Red Bridge into Ville Haute and loops through the centre and the Gare quarter, with music and crowds at hotspots. Dusk turns to night during the race. **Layer idea:** barriers, distance arches, a stream of runners with head-torch-like dots across the Red Bridge and through the old town, and the finish arch at Luxexpo. Image: `ing-night-marathon__2022.jpg`. Website: <https://www.ing-night-marathon.lu>

<a id="autumn"></a>
## Autumn and other events

### Škoda Tour de Luxembourg (cycling) – LOW
**16–20 Sep 2026 (confirmed).** Stage 1 started at the **Knuedler** and finished on the **Fëschmaart** (157.4 km). Stage 5 (Mersch → Luxembourg-Limpertsberg) ended on a circuit with repeated climbs of the Pabeierbierg (830 m at 8.8 %). It was the 86th edition; 2027 dates are not published. *"Luxembourg Open"* in the brief probably refers to the former WTA tennis tournament at Kockelscheuer, which is outside the mapped area and no longer an annual city event. **Layer idea:** a finish arch and sponsor banners on the Fëschmaart, and a peloton sprite. Website: <https://skodatour.lu>

### Nuit des Musées – LOW
**Saturday 10 Oct 2026, 17:00–01:00 (confirmed, 25th edition).** Museums open at night with free shuttles: MNHA and the Lëtzebuerg City Museum (Fëschmaart area), Villa Vauban, Casino, Mudam, Dräi Eechelen, Natur Musée in Grund. 2027: 9 Oct (computed, 2nd Saturday). **Layer idea:** museum facades lit in colours at night, with lanterns along the routes. Website: <https://www.nuit-des-musees.lu>

### Halloween – LOW
No city-wide street event changes the map. Events in 2026: **Halloween weekend at neimënster (Grund) 24–25 Oct**, Halloween concerts for children at the Philharmonie on 24–25 Oct, a Cinémathèque Halloween night on 31 Oct (all confirmed listings). **Layer idea** (the roadmap names Halloween): a playful overlay: pumpkins on doorsteps and window sills in the old town, orange-lit Neimënster, bats over the Alzette valley, small ghosts at the casemate openings in the Bock and Pétrusse cliffs, maybe a witch crossing the moon. It combines well with an autumn-trees season layer.

### All Saints' Day (Allerhellgen) – LOW
1 November, public holiday (Sunday in 2026, Monday in 2027). Families visit graves with chrysanthemums and red grave candles; the largest city cemetery is Notre-Dame cemetery in Limpertsberg (49.6165, 6.1210). **Layer idea:** coloured flower pots and a red candle glow in the cemeteries at dusk.

### Kirchberg and Philharmonie events – LOW
The Kirchberg plateau has Luxexpo fairs, the marathon start, the Sunset Cinema in Parc Kirchberg and the Philharmonie (official National Day ceremony; festivals such as *Rainy Days* contemporary music in late autumn and the autumn *Luxembourg Festival* with the Grand Théâtre). They are indoor or short-lived, so they are not worth separate map layers. A "concert night" glow on the Philharmonie is enough.

<a id="discontinued"></a>
## Discontinued festivals
- **Rock um Knuedler**: a free rock festival on Place Guillaume II each July from the early 1990s. The last edition found is the 29th, on 12 July 2019. Wikipedia notes a gap from 2019 to 2023, and no edition was found for 2024–2026, nor in the 2026 Summer in the City programme.
- **Food For Your Senses (FFYS)**: an independent music, food and art festival that started small, moved several times and ended with a final edition at Kirchberg (late 2010s, probably 2017; Paperjam "Food For Your Senses, dernière").
- **MeYouZik**: see Kinnekswiss above.

These could be "remember when" easter eggs, but they don't need layers.

<a id="historic"></a>
## One-off and historic events (easter eggs or special layers)

| Event | Date | Where | What to draw |
|---|---|---|---|
| **Accession of Grand Duke Guillaume (Trounwiessel)**: abdication of Grand Duke Henri and swearing-in of Guillaume | **3 Oct 2025** (swearing-in at the Chamber of Deputies, balcony appearance at the palace, reception at the Hôtel de Ville, gala dinner); **4 Oct** celebrations in Wiltz, Luxembourg and Dudelange with a concert and **drone show on the Glacis** (a crown drawn in drones); **5 Oct** Te Deum at the cathedral | Chamber of Deputies (49.6103, 6.1343), Palace, Knuedler, Glacis, cathedral | red-white-blue bunting, the joint G+S monogram flags, big screens and crowds in front of the palace, a crown of drones over the Glacis. **HIGH** impact for a "history" layer. Images: `trounwiessel-2025__flags-monograms.jpg`, `__decorated-red-white-blue.jpg`, `__glacis-show.jpg` (drone crown), `__accession-03-10.jpg`. Site: <https://www.trounwiessel.lu> |
| **Royal wedding** of Hereditary Grand Duke Guillaume and Countess Stéphanie de Lannoy | civil wedding 19 Oct 2012 (Hôtel de Ville), religious wedding 20 Oct 2012 (cathedral) | Knuedler, cathedral, palace | flags, flowers, crowds, the couple on the palace balcony. Image: `royal-wedding-2012__cercle-decorated.jpg`; many more CC BY-SA 3.0 lu photos on Commons ("Royal Wedding 2012") |
| **Liberation of Luxembourg City** by US troops | 10 Sep 1944 | Place d'Armes, Cercle | crowds and flags, a US jeep, sepia filter. Image: `liberation-1944__place-darmes-crowds.jpg` (PD, crowds on Place d'Armes acclaiming the Prince and the Hereditary Grand Duke) |
| **Tram opening** | 10 Dec 2017 (Luxexpo – Pont Rouge, in snow) | Kirchberg, Red Bridge | the first tram with a ribbon. Image: `tram-opening-2017__inauguration.jpg` (the Grand Ducal couple cutting the ribbon in snow) |
| **Treaty of London** (neutrality, dismantling of the fortress) | 11 May 1867 | the whole fortress | ties in with the "fortress era" mode (task 4) |
| **Founding**: Count Siegfried acquires the Lucilinburhuc | 963 (millennium celebrated in 1963; 1,100 years in 2063) | Bock | a castle on the Bock with a banner "963" as an easter egg |
| **European Capital of Culture** | 1995 and **2007** (with the Greater Region; "blue deer" logo) | city-wide | blue deer sprites hidden around the map |
| **Big concerts** | e.g. OneRepublic on the Glacis on 23 Jun 2026; City Sounds DJ nights | Glacis, Kinnekswiss | reuse the National Day stage layer |

<a id="plans"></a>
## Layout plans (what exists)
- **Schueberfouer site plan.** The city publishes a plan of the fair with entrances E1–E7, rides and toilets in the yearly programme and the fair's app or web page (fouer.vdl.lu redirects to <https://www.vdl.lu/fr/node/11240>). It is **not freely licensed and no downloadable PDF was found**, so **nothing was downloaded**. A free substitute: the Glacis polygon and allée Scheffer from **OpenStreetMap** (ODbL), plus the photo from the top of the wheel (`schueberfouer__overview-from-big-wheel-2013.jpg`) and the empty-Glacis aerial. The known rules: food in the north-west part, rides elsewhere, seven entrances, the tram line along the south-east edge (layout fixed since 2017).
- **Winterlights market map.** The city and the tourist office (LCTO) publish a programme leaflet with a map of the market sites (the 2025 LCTO press release PDFs are at <https://www.luxembourg-city.com/media/da0d1320-4b5d-4c24-9419-b9b11ea67038/20251120-lcto-compresse-winterlights.pdf> and the German version `…/7b4dd3a7-…/20251120-lcto-pressemitteilung-winterlights.pdf`). The map is not free; the site list above is enough to place the layer, and the squares are in OSM.
- **National Day.** The city publishes a diversion and closure map for the torchlight procession, fireworks and parade (vdl.lu, around 15–20 June). It is not free; the route is described above.
- **Octave.** Programme PDFs with times: <https://www.cathol.lu/fileadmin/user_upload/DOCUMENTS/Oktav-Programm/Programme_OCTAVE_FR._2026_pdf.pdf> (DE: `Programm_OKTAV_DE._2026_pdf.pdf`). Text only, no route map found.
- **Summer in the City 2026** programme press release: <https://www.luxembourg-city.com/media/1c200041-10d1-4c9c-a0da-c55b1427e4c2/20260609-lcto-compresse-programme-summer-in-the-city-2026.pdf>

<a id="images"></a>
## Images (51)
All are listed in `sources.json` with author and licence. By event: Schueberfouer 13, Winterlights 11, National Day 6, Octave 4, Trounwiessel 2025 4, Éimaischen 2, Buergbrennen 2, Blues'n Jazz Rallye 2, and one each for fireworks (generic), carnival, Fête de la Musique, ING Night Marathon, royal wedding 2012, liberation 1944 and tram opening 2017. The best references **from above** are `schueberfouer__overview-from-big-wheel-2013.jpg`, `winterlights__wantermaart-2025-a.jpg` / `-b.jpg` and `schueberfouer__glacis-empty-aerial.jpg`.

**Gaps:** there is no free photo of the National Day fireworks over the Pétrusse, no drone or aerial photo of the whole Schueberfouer, no free photo of the Octave closing procession (apart from the 1893 drawing), and no usable Pride crowd photo. All of these can be found in press galleries (Chronicle.lu, Paperjam, Luxembourg Times, vdl.lu) as links only.

<a id="top5"></a>
## Recommendation: the first 5 layers to build

1. **Winterlights** (20 Nov – 3 Jan, about 6.5 weeks). It is the longest-running event, it changes several central squares at once (chalet rings, the big wheel by the Gëlle Fra, ice rink, trees), it looks best at night (it pairs with the night layer) and with the snow and winter-trees seasons, and it covers New Year's Eve too.
2. **Schueberfouer** (21 Aug – 9 Sep, 20 days). It is the single biggest visual change: a 4.4 ha empty car park becomes a dense, colourful funfair with a big wheel, about 2 million visitors and animated rides. It sits in one clear polygon, so it is easy to place.
3. **National Day, eve and day** (22–23 June). Fireworks over the Pétrusse from Pont Adolphe, torchlight procession, flags everywhere, and the parade on avenue de la Liberté. It is short but the most emblematic. Build the flags as a reusable "national flags" sub-layer (also for the Trounwiessel and royal easter eggs).
4. **Octave and Mäertchen** (about 2 weeks in spring). It fills the spring gap and reuses the market-stall sprites from Winterlights on the Knuedler, plus a procession sprite at the cathedral. Add **Éimaischen** (Fëschmaart stalls with bird whistles) as a one-day variant with the same assets.
5. **Halloween** (late October), as a requested extra. There is no real city event, so it is a stylised layer (pumpkins, bats, ghosts at the casemates) that is cheap to make and pairs with autumn trees. If an event-faithful option is wanted instead, the **Blues'n Jazz Rallye** valley night is the best summer alternative.

Cheap extras that reuse these assets: Fête de la Musique and Kinnekswiss loves (stages), the Buergbrennen bonfires (one fire sprite), Pride (rainbow flags on the flag sub-layer) and the marathon (barriers and a runner stream).

<a id="sources"></a>
## Sources (dates and facts)
- City of Luxembourg, Winterlights page (dates 20 Nov 2026 – 3 Jan 2027): <https://www.vdl.lu/en/visiting/leisure-and-recreation/festivals-fairs-and-events/winterlights-0>
- Chronicle.lu, "City Winterlights 2025 to feature markets, ice rink, royal tree, Kleeschen tour": <https://chronicle.lu/category/things-to-see-do/57888-city-winterlights-2025-to-feature-markets-ice-rink-royal-tree-kleeschen-tour>
- Chronicle.lu, "Fireworks rules vary across Luxembourg on New Year's Eve" (2025): <https://chronicle.lu/category/at-home/58728-fireworks-rules-vary-across-luxembourg-on-new-years-eve>
- Chronicle.lu, "Schueberfouer 2026 to feature 214 fairground establishments": <https://chronicle.lu/category/things-to-see-do/62671-schueberfouer-2026-to-feature-214-fairground-establishments-8-new-attractions>
- Paperjam, "Schueberfouer 2026: 214 stalls and four new rides": <https://en.paperjam.lu/article/schueberfouer-2026-214-stalls-and-four-new-rides>
- Lesfrontaliers.lu, key dates 2026: <https://www.lesfrontaliers.lu/detente/schueberfouer-les-grandes-dates-a-ne-pas-manquer-lors-de-ledition-2026/>
- Chronicle.lu, poster competition 2026–2028: <https://chronicle.lu/category/things-to-see-do/59746-luxembourg-city-launches-competition-for-2026-2028-schueberfouer-posters>
- Government of Luxembourg, National Day 2026 eve: <https://gouvernement.lu/en/actualites/toutes_actualites/communiques/2026/06-juin/22-fete-nationale-2026-veille.html>
- Chronicle.lu, updated National Day 2026 programme: <https://chronicle.lu/category/at-home/61909-luxembourg-announces-updated-national-day-2026-programme> and "VdL expects up to 30k visitors": <https://chronicle.lu/category/at-home/61816-vdl-unveils-national-day-2026-programme-expects-up-to-30k-visitors>
- Paperjam, how Luxembourg celebrates National Day (fireworks photo, not free): <https://en.paperjam.lu/article/how-luxembourg-celebrates-nati>
- cathol.lu, Octave 2026 programme: <https://www.cathol.lu/fileadmin/user_upload/DOCUMENTS/Oktav-Programm/Programme_OCTAVE_FR._2026_pdf.pdf>; Wikipedia "Oktav": <https://en.wikipedia.org/wiki/Oktav>
- City of Luxembourg, Mäertchen on Place Guillaume II: <https://www.vdl.lu/en/node/342419>
- Chronicle.lu, Éimaischen 2026: <https://chronicle.lu/category/things-to-see-do/60510-luxembourgs-197th-emaischen-festival-draws-crowds-features-workshops-in-city-centre>
- Paperjam, Buergbrennen 2026: <https://paperjam.lu/article/buergbrennen-2026>; Chronicle.lu Buergbrennen 2026: <https://chronicle.lu/category/at-home/59695-buergbrennen-bonfires-light-up-luxembourg-ahead-of-spring>
- LCTO, Summer in the City 2026 press release (PDF, link above)
- Chronicle.lu, Fête de la Musique 2026 line-up: <https://chronicle.lu/category/festivals/61609-luxembourg-city-unveils-2026-fete-de-la-musique-lineup>
- Chronicle.lu, 30th Blues'n'Jazz Rallye: <https://chronicle.lu/category/culture/62479-30th-edition-of-luxembourgs-bluesn-jazz-rallye>
- City of Luxembourg, City Open Air Cinema: <https://www.luxembourg-city.com/en/what-s-on/event/city-open-air-cinema>
- Luxembourg Pride Week 2026: <https://www.luxembourgpride.lu/pride-week-2026>
- ING Night Marathon (VisitLuxembourg 2026 listing): <https://www.visitluxembourg.com/event/ing-night-marathon-luxembourg>; Chronicle.lu "expects record 18k participants": <https://chronicle.lu/category/athletics/61115-19th-ing-night-marathon-luxembourg-expects-record-18k-participants>
- Nuit des Musées 2026 (VisitLuxembourg): <https://www.visitluxembourg.com/event/nuit-des-musees-2026>
- Škoda Tour de Luxembourg 2026 stages: <https://skodatour.lu/all-stages/>
- Halloween at neimënster 2026 (VisitLuxembourg): <https://www.visitluxembourg.com/event/halloween-2>
- Trounwiessel programme: <https://monarchie.lu/en/accession-throne-trounwiessel-programme>; Chronicle.lu "concerts, drone show": <https://chronicle.lu/category/things-to-see-do/56971-luxembourg-city-announces-concerts-drone-show-tram-spectacle-for-throne-transition>
- Rock um Knuedler (Wikipedia): <https://en.wikipedia.org/wiki/Rock_um_Knuedler>; Paperjam, last FFYS: <https://paperjam.lu/article/food-for-your-senses-derniere>
