# 06 – City details: facts, quarters, important buildings, monuments, easter eggs

The factual backbone for info panels, search and easter eggs: city facts, the 24 official quarters with boundaries and 2025 population, 80 important buildings beyond the 47 landmarks of task 1, the national protected-monument list for the city, and 40 easter-egg stories with coordinates.

Related folders (not repeated here): [01-landmarks](../01-landmarks/README.md) (47 landmarks with photos: palace, cathedral, Bock, bridges, Philharmonie, Mudam, Court of Justice, d'Coque, Gare…), [02-buildings-interiors](../02-buildings-interiors/README.md) (interiors and plans of 22 buildings incl. Grand Théâtre, Villa Vauban, National Library), [03-underground-tunnels](../03-underground-tunnels/README.md) (casemates, lifts, tunnels), [04-city-evolution](../04-city-evolution/README.md) (fortress eras, 1867 dismantling, 1920 mergers), [05-events](../05-events/README.md) (Schueberfouer, National Day, Octave…).

How to use this folder:
- `data/quarters.geojson`: the city's official 24 quarter polygons (WGS84) with `name`, `name_lb`, `population` (31 Dec 2025), `pct_luxembourgish`, `top_nationalities`, `area_km2`, `density_per_km2`, a label point, a short `character`, `landmarks`, and the ids of buildings from `buildings.json` that fall inside. Boundary licence: CC BY (Ville de Luxembourg). The map's `QUARTERS` list in `pipeline/build_places.py` uses only 6 names; these 24 are the official set and can replace it (note that OSM spells some differently, e.g. Mühlenbach / Pulvermühl).
- `data/buildings.json`: 80 records `{id, name, name_local, address, lat, lon, year, architect, use, quarter, description, wikipedia, wikidata, heritage}`. `quarter` comes from point-in-polygon on the official boundaries. `heritage` is set only when the building matches an entry on the national protected list (status code, list id, date). `year`/`architect` are `null` where no reliable source was found. 70 buildings + 10 embassies.
- `data/monuments.csv` and `data/monuments.geojson`: the national protected list for the city (397 rows, 380 with usable points) parsed from the Luxembourgish Wikipedia lists, which follow the official INPA list (see below). `data/monuments_inpa_polygons.geojson`: the official INSPIRE parcels (238 polygons, CC0) from the Géoportail, with INPA's short codes only.
- `data/easter_eggs.json`: 40 records `{id, title, story, lat, lon, source, kind}`.
- `data/tram_t1_stops.json`: the 24 stops of tram line T1 in order (OSM). `data/fountains_vdl.geojson`: the city's 31 public fountains (city open data).
- `images/` + `sources.json`: 14 freely licensed Commons photos (1600 px) of buildings and quarters not covered by tasks 1–2. Attribution needed for CC BY-SA files.
- Coordinates are WGS84. Figures are dated; checked on 6 Nov 2026.

## City facts

| | |
|---|---|
| Official name | Ville de Luxembourg / Stad Lëtzebuerg / Stadt Luxemburg; the capital of the Grand Duchy and its most populous commune |
| Area | **51.73 km²** (about 2% of the country), circumference 52.5 km. Land use: 30% built up, 27.7% farmland, 22% forest, 8.7% streets and squares, 1.5% industry, 0.7% water (city, Facts and figures). Until the 1920 mergers with Eich, Hamm, Hollerich and Rollingergrund the city covered only 3.55 km² |
| Population | **137,696** inhabitants on 31 Dec 2025 (Ville de Luxembourg population register; 136,208 end 2024, 93,865 end 2010). Women 48.38%, men 51.62%. Births 1,277, deaths 604, arrivals 18,485, departures 13,773 in 2025. STATEC publishes its own commune figures (as of 1 January) which differ slightly from the city register; Wikipedia quotes ~139,000 for Oct 2026 |
| Nationalities | **30.52% Luxembourgers (42,020), 69.48% foreigners (95,676), 168 nationalities.** Largest foreign groups: French 20,638, Portuguese 10,795, Italian 10,261, Spanish 5,428, Belgian 4,151, German 3,644, Romanian 2,346, Greek 2,233, Polish 1,748, Irish 1,147. By continent: 119,651 Europeans, 8,856 Asians, 5,405 Africans, 3,542 Americans, 159 Oceanians (31 Dec 2025) |
| Coordinates | 49°36′36″N, 6°7′40″E |
| Elevation | from **232 m** (Beggen, rue de Bastogne, Alzette valley) to **408 m** (Dommeldange plateau); Place d'Armes 304 m. The Alzette and Pétrusse gorges are about 70 m deep |
| Rivers | **Alzette** (Uelzecht), flowing north through Hesperange, Pulvermuhl, Grund, Pfaffenthal, Eich, Dommeldange and Beggen; **Pétrusse** (Péitruss), a small brook in a park valley under the Adolphe Bridge and the Passerelle, joining the Alzette in the Grund |
| UNESCO | **"City of Luxembourg: its Old Quarters and Fortifications"**, World Heritage List since **1994** (site 699): the Ville Haute, the Grund, Pfaffenthal and Clausen fortifications. See tasks 1, 3, 4 |
| Languages | Luxembourgish (national language); Luxembourgish, French and German are all administrative languages (law of 24 Feb 1984); French dominates street signs and laws, and English is widely used in business and EU circles |
| Mayor | **Lydie Polfer** (DP), mayor since 17 Dec 2013 (also 1982–1999); she leads the college of aldermen (mayor + 6 aldermen, a special allowance for the capital) in a DP–CSV coalition |
| Council | 27 members (fixed since 1964); the DP has 10 seats and has supplied every mayor since 1969. Last communal elections 11 June 2023; next in 2029 |
| Head of state | Grand Duke **Guillaume** since 3 Oct 2025 (see task 5: Trounwiessel) |
| City staff | 4,666 (1 Jan 2026), about 50 departments |
| Twin cities | **Metz** (France) and **Prague** (Czech Republic), as listed on Wikipedia (Tambov Oblast is also listed there but unsourced). The city's own "Networks and partnerships" page was not readable (HTTP 403) |
| Coat of arms | Blazon (fr. Wikipedia): *D'argent à cinq burelles d'azur au lion de gueules couronné d'or brochant, l'écu timbré d'une couronne d'or*: a red lion with a gold crown on silver and blue horizontal stripes, under a gold crown. So the arms' colours are silver/white, blue, red and gold; the city's modern logo uses a stylised red lion. The city's own flag colours were not confirmed by a primary source |
| Motto | **"Mir wëlle bleiwe wat mir sinn"** ("We want to remain what we are"), the national motto, from Michel Lentz's 1859 song *De Feierwon* written for the arrival of the railway. Lentz also wrote the words of the anthem *Ons Heemecht*; see the Dicks-Lentz monument easter egg |
| Free public transport | All buses, trams and trains in the country have been free since **29 February 2020**. The city bus service (AVL) runs about 30 lines plus a night network. Its own fleet is 72 standard buses (52 electric) and 58 articulated buses (20 electric), and subcontractors add 160 electric buses (city, 2026) |
| Tram | Line **T1**, 16.4 km, **24 stops**, Findel airport ↔ Stadion (Stade de Luxembourg) in about 34 min. Opened 10 Dec 2017 (Luxexpo–Rout Bréck), then to the Étoile (27 Jul 2018), Gare Centrale (Dec 2020) and Lycée Bouneweg (11 Sep 2022), then on south to Stadion; the full line to the airport has run since **2 March 2025**. Run by Luxtram (two-thirds state, one-third city). It runs 3.6 km through the centre without overhead wires (supercapacitors). Branches to Laangfur (Kirchberg) and Nei Hollerich are planned for 2027–28; 4 lines by 2035 |
| EU seat | One of the EU's three official seats: Court of Justice, Court of Auditors, European Investment Bank and Fund, European Parliament secretariat, ESM, EPPO, Eurostat, Publications Office; the Council of the EU meets here in April, June and October |
| Culture capital | European Capital of Culture 1995 and 2007 (the first city to be chosen twice) |

### Tram T1 stops (north to south)

1. Findel - Luxembourg Airport → 2. Héienhaff P+R → 3. Luxexpo → 4. Alphonse Weicker → 5. Nationalbibliothéik / Bibliothèque nationale → 6. Universitéit → 7. Coque → 8. Europaparlament / Parlement européen → 9. Philharmonie - MUDAM → 10. Rout Bréck - Pafendall → 11. Theater → 12. Faïencerie → 13. Stäreplaz / Étoile → 14. Hamilius → 15. Place de Metz → 16. Paräisser Plaz / Place de Paris → 17. Gare Centrale → 18. Leschte Steiwer / Dernier Sol → 19. Lycée Bouneweg → 20. Scillas → 21. Gare Howald → 22. Lycée Vauban → 23. Waassertuerm → 24. Stadion

The 2 northern stops (airport, Héienhaff P+R) are outside the city in Sandweiler/Niederanven. Gare Howald is in Hesperange.

## The 24 quarters

Official quarters of the city, with boundaries from the city's open data and populations from the city population register on **31 Dec 2025**. Area is computed from the polygons (sum 51.3 km², official 51.73 km²). The numbering follows the city's population report.

| # | Quarter (French) | Luxembourgish | Pop. 2025 | % Lux. | km² | per km² | Character | Landmark buildings |
|---|---|---|---:|---:|---:|---:|---|---|
| 1 | **Beggen** | Beggen | 3,844 | 33.9 | 1.7 | 2,267 | Northern quarter along the Alzette valley and route de Mersch, with an old village core, villas and newer housing. The city's lowest point (232 m, rue de Bastogne) is here. | Château de Beggen (Russian embassy), Beggen church |
| 2 | **Belair** | Belair | 13,331 | 33.4 | 1.7 | 7,823 | Leafy, well-off residential quarter west of the old town, built up from around 1900 along route d'Arlon and avenue Gaston Diderich. Villas, embassies and the old national stadium. | Stade Josy Barthel, Embassy villa belt (rue Marie-Adélaïde, rue des Girondins), Saint Pius X church (protection procedure opened Sept 2026) |
| 3 | **Bonnevoie-Nord / Verlorenkost** | Bouneweg-Nord / Verluerekascht | 4,581 | 28.1 | 0.67 | 6,815 | The northern part of Bonnevoie on the plateau between the railway and the Alzette valley, with the Verlorenkost housing area. Railway heritage defines it: the Rotondes roundhouses sit at its edge. | Rotondes |
| 4 | **Bonnevoie-Sud** | Bouneweg-Süd | 13,428 | 33.9 | 2.37 | 5,664 | The most populous quarter: dense, lively and multicultural streets south-east of the station, with the CFL workshops along the tracks. The tram runs through it on the new N3 alignment past the Lycée Bouneweg. | Banannefabrik, Lycée technique de Bonnevoie, CFL central workshops, Ubu roi sculpture (rue de Bonnevoie) |
| 5 | **Cents** | Zens | 6,618 | 50.4 | 1.72 | 3,855 | Quiet residential plateau east of the city with houses and gardens. It is the only quarter where Luxembourgers are the majority (50.4%). | Carmelite convent, Cents-Hamm station |
| 6 | **Cessange** | Zessengen | 5,214 | 33.7 | 6.53 | 799 | Former village in the south-west, now mostly residential, bordering the Cloche d'Or business district and the A4/A6 motorways. | Bëschkierfecht (forest cemetery), Saint Joseph's church |
| 7 | **Clausen** | Klausen | 1,050 | 28.0 | 0.36 | 2,935 | Small valley quarter on the Alzette below Kirchberg and the Bock. The old Mousel brewery is now the 'Rives de Clausen' bar district; Robert Schuman was born here. | Mansfeld castle ruins and park, Robert Schuman's birthplace, Malakoff tower, Clausen viaduct, German military cemetery |
| 8 | **Dommeldange** | Dummeldeng | 3,106 | 27.3 | 2.34 | 1,329 | Northern valley quarter with an industrial past (the Dommeldange ironworks) at the edge of the Grünewald forest, served by its own railway station. | Dommeldange station, former ironworks (Dummeldenger Schmelz), Dommeldange parish church |
| 9 | **Eich** | Eech | 3,079 | 30.0 | 0.63 | 4,913 | Old valley village north of Pfaffenthal, a former separate commune that merged with the city in 1920, built around place Dargent. | Place Dargent (Perlia pharmacy, 1866), CHL Eich hospital, old forge (Eecherschmelz) |
| 10 | **Gare** | Gare (Garer Quartier) | 11,292 | 18.4 | 1.04 | 10,816 | Grew after the railway arrived in 1859, with grand Belle Époque and Art Nouveau buildings along avenue de la Liberté. The most international quarter: only 18.4% Luxembourgers, and the French outnumber them. | Gare Centrale, Spuerkeess tower, ARBED building, Villa Pauly, Rousegäertchen (place des Martyrs), Sacré-Cœur church |
| 11 | **Gasperich** | Gaasperech | 10,282 | 29.1 | 4.42 | 2,328 | Old village core in the south, plus the new Ban de Gasperich / Cloche d'Or business district: offices, flats, a shopping centre and the national stadium, all built since the 2010s. | Stade de Luxembourg, Cloche d'Or shopping centre, CNIS fire and rescue centre, PwC Crystal Park |
| 12 | **Grund** | Gronn | 983 | 43.7 | 0.3 | 3,300 | The picturesque lower town on the Alzette, deep below the Corniche and the Saint-Esprit plateau: old houses, pubs, the abbey and the river. It has one of the highest shares of Luxembourgers (43.7%). | Neumünster Abbey, Saint-Jean du Grund, Natur Musée, Stierchen bridge, Grund lift, Melusina statue |
| 13 | **Hamm** | Hamm | 1,606 | 43.1 | 4.04 | 397 | Semi-rural former commune on the eastern edge, merged in 1920, next to Findel airport. Its best-known site is the American military cemetery where General Patton is buried. | Luxembourg American Cemetery (Patton's grave), Hamm crematorium, Fort Dumoulin remains |
| 14 | **Hollerich** | Hollerech | 7,751 | 28.1 | 1.59 | 4,884 | Former commune (merged 1920) south-west of the station, long industrial and now being rebuilt as 'Nei Hollerich'. Concert venues, the bus depot and the Geesseknäppchen school campus. | Den Atelier, Tram and Bus Museum, Athénée, BIL headquarters, Saints Peter and Paul church, P+R Bouillon |
| 15 | **Kirchberg** | Kierchbierg | 10,982 | 25.5 | 3.34 | 3,287 | Plateau across the Red Bridge, developed from the 1960s by the Fonds Kirchberg for the European institutions, then banks, culture and housing. Ukrainians are the second-largest nationality here. | Philharmonie, Mudam, Court of Justice towers, European Investment Bank, d'Coque, Luxexpo, Fort Thüngen, Kirchberg shopping centre |
| 16 | **Limpertsberg** | Lampertsbierg | 11,593 | 29.1 | 1.56 | 7,441 | Residential plateau north-west of the old town, on land freed by the fortress glacis. Schools, Art Nouveau houses on avenue Pasteur, the Glacis where the Schueberfouer is held, and the Grand Théâtre. | Grand Théâtre, Glacis, Lycée de garçons, Lycée Robert-Schuman, Saint Joseph's church, Lycée des Arts et Métiers |
| 17 | **Merl** | Märel | 6,602 | 31.8 | 2.41 | 2,741 | Green residential quarter in the west around the large Parc de Merl, with the city conservatoire and the 'Celtes' area. | Parc de Merl, Conservatoire, Merl church (Saint Gengoul) |
| 18 | **Muhlenbach** | Millebaach | 2,528 | 32.2 | 3.09 | 819 | Small valley quarter in the north-west between Rollingergrund and Eich, named after its mill brook. | Saint-Fiacre church |
| 19 | **Neudorf / Weimershof** | Neiduerf / Weimeschhaff | 7,178 | 25.2 | 2.47 | 2,907 | Neudorf stretches along the long rue de Neudorf in the valley east of Clausen; Weimershof sits on the plateau next to Kirchberg. | former Henri Funck brewery buildings, Saint-Henri church, Hôpital Kirchberg (edge) |
| 20 | **Pfaffenthal** | Pafendall | 1,380 | 39.1 | 0.37 | 3,708 | Valley quarter directly under the Red Bridge and the old town's northern walls, with Vauban's gates. Since 2016–2017 a panoramic lift and a funicular link it to the old town and Kirchberg. | Pfaffenthal panoramic lift, Pfaffenthal-Kirchberg station and funicular, Eich gate and Bons-Malades gate, Hospice civil, Saint-Mathieu church |
| 21 | **Pulvermuhl** | Polvermillen | 386 | 29.5 | 0.25 | 1,568 | The smallest quarter (386 people), deep in the Alzette valley south-east of the Grund around the Pulvermühl railway viaduct. The name means 'gunpowder mill'. | Pulvermühl viaduct (1862), Saints Cosmas and Damian church, former gendarmerie barracks (rue Auguste Lumière) |
| 22 | **Rollingergrund / Belair-Nord** | Rollengergronn / Belair-Nord | 4,898 | 29.4 | 6.29 | 779 | North-western valley quarter running towards the Bambësch forest, with the old Villeroy & Boch porcelain works and the main CHL hospital site. | Château de Septfontaines (Villeroy & Boch), CHL hospital, CHL Maternité (Bauhaus, 1936) |
| 23 | **Ville Haute** | Uewerstad (Stad) | 3,513 | 31.9 | 1.05 | 3,344 | The old town on its rock: the core of the UNESCO site, with the palace, the cathedral, the main squares, shopping on the Grand-Rue and banks on boulevard Royal. Only about 3,500 people live here. | Grand Ducal Palace, Notre-Dame Cathedral, Place d'Armes, Place Guillaume II, Bock casemates, Chemin de la Corniche, Gëlle Fra, Cité judiciaire |
| 24 | **Weimerskirch** | Weimeschkierch | 2,471 | 31.8 | 1.1 | 2,254 | Hillside quarter in the north between Eich and Kirchberg, around its old village church and cemetery. | Weimerskirch church, Raspert |

Top four nationalities by quarter are in `top_nationalities`. Highlights: Gare is the only quarter where the French (2,265) outnumber the Luxembourgers (2,079); Cents is the only one with a Luxembourgish majority (50.4%); Kirchberg has 1,016 Ukrainian residents, its second-largest group; Bonnevoie-Sud (13,428) and Belair (13,331) are the most populous; Pulvermuhl (386) and Grund (983) the smallest.

## Important buildings (80), by quarter

All are in `data/buildings.json` with coordinates, descriptions and links. ★ = on the national protected list (status in brackets: MN = classified national monument, IS = supplementary inventory, PCN = national cultural heritage under the 2022 law). Task-1 landmarks are left out on purpose.

### Beggen

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Château de Beggen (Embassy of Russia)](https://en.wikipedia.org/wiki/Embassy_of_Russia,_Luxembourg) | – | – | embassy of the Russian Federation | 116A rue Cyprien Merjai, Beggen |

### Belair

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Stade Josy Barthel](https://en.wikipedia.org/wiki/Stade_Josy_Barthel) | 1928–1931 | – | former national stadium (to 2021) | route d'Arlon |

### Bonnevoie-Nord / Verlorenkost

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Rotondes](https://en.wikipedia.org/wiki/Rotondes_(Luxembourg)) ★ (MN) | 1877 | – | cultural centre (former railway roundhouses) | Place des Rotondes, Bonnevoie |

### Bonnevoie-Sud

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Banannefabrik](https://lb.wikipedia.org/wiki/Banannefabrik) | 1960 | Robert-F. Heintz-Sturm | dance and theatre production centre | 12 rue du Puits, Bonnevoie |

### Clausen

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Mansfeld Castle ruins (La Fontaine)](https://en.wikipedia.org/wiki/La_Fontaine_Castle) ★ (MN) | from 1563 | – | ruins and park | allée Pierre de Mansfeld, Clausen |
| [Robert Schuman's birthplace](https://en.wikipedia.org/wiki/Robert_Schuman) | (born here 29 June 1886) | – | memorial house | rue Jules Wilhelm, Clausen |
| [Malakoff Tower](https://lb.wikipedia.org/wiki/Malakoff-Tuerm_(Lëtzebuerg)) | 1861 | – | fortress tower (now association premises) | rue Jules Wilhelm, Clausen |
| [German military cemetery, Clausen](https://en.wikipedia.org/wiki/Clausen_German_war_cemetery) | 19th century | – | war cemetery | rue Jules Wilhelm, Clausen |

### Gare

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [ARBED building ('19 Liberté')](https://lb.wikipedia.org/wiki/Arbedsgebai) ★ (MN) | 1920s | René Théry (works by Sosthène Weis) | former ARBED steel group headquarters; Spuerkeess since 2014 | 19 avenue de la Liberté |
| [Villa Pauly](https://en.wikipedia.org/wiki/Villa_Pauly) ★ (MN) | 1923 | Mathias Martin | Resistance documentation centre (since 2001); Gestapo headquarters 1940–1944 | 57 boulevard de la Pétrusse |
| [Villa Clivio](https://lb.wikipedia.org/wiki/Lëscht_vun_den_nationale_Monumenter_an_der_Gemeng_Lëtzebuerg/Quartier_Gare) ★ (MN) | early 20th century | Mathias Martin | offices | 17 rue Goethe |
| [Sacred Heart Church (Gare parish church)](https://lb.wikipedia.org/wiki/Kierch_Lëtzebuerg-Gare) | 1930–1936 | Nicolas Petit | Catholic parish church | rue Dicks / boulevard de la Pétrusse |
| [Publications Office of the EU](https://en.wikipedia.org/wiki/Publications_Office_of_the_European_Union) | – | – | EU publisher (Official Journal) | 20 rue de Reims |
| [Den Atelier](https://en.wikipedia.org/wiki/Den_Atelier) | 1995 | – | concert hall | 54 rue de Hollerich |
| Embassy of Netherlands | – | – | embassy | 6 rue Sainte-Zithe |

### Gasperich

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Stade de Luxembourg](https://en.wikipedia.org/wiki/Stade_de_Luxembourg) | 2017–2021 | gmp (von Gerkan, Marg & Partner) with Beng Architectes | national football and rugby stadium | 100 boulevard de Kockelscheuer |
| [Cloche d'Or shopping centre](https://lb.wikipedia.org/wiki/Cloche_d'or) | 2019 | – | shopping centre | 25 boulevard F.W. Raiffeisen |
| [National fire and rescue centre (CNIS)](https://fr.wikipedia.org/wiki/Centre_national_d'incendie_et_de_secours) | – | – | fire station, 112 emergency centre, training | 3 boulevard de Kockelscheuer |
| PwC 'Crystal Park' | 2014 | – | offices (PwC Luxembourg) | 2 rue Gerhard Mercator |

### Hamm

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Luxembourg American Cemetery and Memorial](https://en.wikipedia.org/wiki/Luxembourg_American_Cemetery_and_Memorial) | 1960 | – | war cemetery | 50 val du Scheid, Hamm |

### Hollerich

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [BIL headquarters](https://en.wikipedia.org/wiki/Banque_Internationale_à_Luxembourg) | – | – | bank headquarters | 69 route d'Esch |
| [Athénée de Luxembourg](https://en.wikipedia.org/wiki/Athénée_de_Luxembourg) | 1964 (building); school founded 1603 | – | secondary school | 24 boulevard Pierre Dupong |
| [Lycée Michel-Rodange](https://en.wikipedia.org/wiki/Lycée_Michel_Rodange) | 1968 | Laurent Schmit and Jim Clemes (per Wikidata) | secondary school | boulevard Pierre Dupong |
| [Tram and Bus Museum](https://fr.wikipedia.org/wiki/Musée_des_tramways_et_de_bus_de_la_ville_de_Luxembourg) | 1991 | – | museum (free) | 63 rue de Bouillon |
| Embassy of Belgium | – | – | embassy | 4 rue des Girondins |
| Embassy of Italy | – | – | embassy | 5–7 rue Marie-Adélaïde |

### Kirchberg

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [European Investment Bank](https://en.wikipedia.org/wiki/European_Investment_Bank) | 1980 (west building); 2008 (east building) | Denys Lasdun (west building); Christoph Ingenhoven (east building) | EU bank headquarters | 98–100 boulevard Konrad Adenauer |
| [European Court of Auditors](https://en.wikipedia.org/wiki/European_Court_of_Auditors) | – | – | EU institution | 12 rue Alcide de Gasperi |
| [Eurostat (Bech building)](https://en.wikipedia.org/wiki/Eurostat) | – | – | European Commission (Eurostat, the EU statistical office) | rue Alphonse Weicker |
| [Jean Monnet 2 building (European Commission)](https://lb.wikipedia.org/wiki/Jean-Monnet-2-Gebai) | construction from 2018 | KSP Jürgen Engel Architekten | European Commission offices (about 3,600 workplaces) | boulevard Konrad Adenauer |
| [Alcide De Gasperi building](https://en.wikipedia.org/wiki/Alcide_De_Gasperi_building) | 1960–1965 | Michel Mousel and Gaston Witry | EU offices (European Parliament secretariat until 2001) | Place de l'Europe |
| [Robert Schuman building](https://lb.wikipedia.org/wiki/Robert-Schuman-Gebai) ★ (PCN) | 1970–1973 | Laurent Schmit | European Parliament offices; plenary hall 1973–1979 | 2 place de l'Europe |
| [European Convention Center Luxembourg (ECCL)](https://en.wikipedia.org/wiki/European_Convention_Center_Luxembourg) | – | – | conference centre; meetings of the Council of the EU in April, June and October | 4 place de l'Europe |
| [Luxexpo The Box](https://fr.wikipedia.org/wiki/Luxexpo_The_Box) | c. 1970 (halls) | – | exhibition and congress centre | 10 Circuit de la Foire Internationale |
| [Chamber of Commerce](https://en.wikipedia.org/wiki/Luxembourg_Chamber_of_Commerce) | – | – | chamber of commerce and conference centre | 7 rue Alcide de Gasperi |
| Deutsche Bank building ★ (PCN) | 1991 | Gottfried Böhm | bank offices | 2 boulevard Konrad Adenauer |
| HypoVereinsbank / UniCredit building | 1993 | Richard Meier | bank offices | 4 rue Alphonse Weicker |
| [Infinity tower](https://lb.wikipedia.org/wiki/Infinity_(Kierchbierg)) | 2017–2020 | Arquitectonica (Bernardo Fort-Brescia) | flats, offices, shops | avenue John F. Kennedy / rue du Fort Niedergrünewald |
| [European School Luxembourg I](https://en.wikipedia.org/wiki/European_School,_Luxembourg_I) | 1953 (school) | – | school for children of EU staff | 23 boulevard Konrad Adenauer |
| [Kinepolis Kirchberg](https://en.wikipedia.org/wiki/Kinepolis_Kirchberg) | 1996 | – | multiplex cinema | 45 avenue John F. Kennedy |
| [European Stability Mechanism](https://en.wikipedia.org/wiki/European_Stability_Mechanism) | – | – | EU financial institution | 6A Circuit de la Foire Internationale |

### Limpertsberg

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Lycée de garçons de Luxembourg (LGL)](https://en.wikipedia.org/wiki/Lycée_de_Garçons_de_Luxembourg) ★ (IS) | 1892 (school) | – | secondary school | Place Auguste Laurent / 41A avenue Victor Hugo |
| [Lycée Robert-Schuman](https://lb.wikipedia.org/wiki/Lycée_Robert-Schuman) ★ (IS) | 1909 (school); building 1920s | Nicolas Petit (per Wikidata, with Laurent Schmit) | secondary school | 1 boulevard Emmanuel Servais |
| [Lycée des Arts et Métiers](https://lb.wikipedia.org/wiki/Lycée_des_arts_et_métiers) | 1910–1911 | Sosthène Weis (workshops) | secondary / technical school | 19 rue Guillaume Schneider |
| [Saint Joseph's Church, Limpertsberg](https://en.wikipedia.org/wiki/St_Joseph's_Church,_Limpertsberg) ★ (MN) | 1910–1913 | Nicolas Petit | Catholic parish church | 43A avenue Victor Hugo |
| [Embassy of United States](https://en.wikipedia.org/wiki/Embassy_of_the_United_States,_Luxembourg) | – | – | embassy | 22 boulevard Emmanuel Servais |
| Embassy of Japan | – | – | embassy | 62 avenue de la Faïencerie |

### Merl

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Conservatoire de la Ville de Luxembourg](https://en.wikipedia.org/wiki/Conservatoire_de_Luxembourg) | 1984 (this building); founded 1906 | – | music school and concert hall | 33 rue Charles Martel |
| Embassy of Portugal | – | – | embassy | 282 route de Longwy |

### Neudorf / Weimershof

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Hôpital Kirchberg](https://lb.wikipedia.org/wiki/Hôpital_Kirchberg) | 2003 | – | hospital (Hôpitaux Robert Schuman) | 9 rue Edward Steichen |

### Pfaffenthal

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Hospice civil, Pfaffenthal](https://lb.wikipedia.org/wiki/Lëscht_vun_den_nationale_Monumenter_an_der_Gemeng_Lëtzebuerg/Pafendall) ★ (MN) | – | – | old people's home; church with a protected 1843 Wetzel organ | rue Mohrfels, Pfaffenthal |

### Rollingergrund / Belair-Nord

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Centre Hospitalier de Luxembourg (CHL)](https://en.wikipedia.org/wiki/Centre_Hospitalier_de_Luxembourg) | 1975 | – | main public hospital | 4 rue Nicolas-Ernest Barblé |
| [CHL Maternité (Maternité Grande-Duchesse Charlotte)](https://en.wikipedia.org/wiki/Grand_Duchess_Charlotte_Maternity_Hospital) | 1936 | Otto Bartning with Pali Meller; executed by Hubert Schumacher | maternity hospital | 2 rue Pierre Federspiel |
| [Château de Septfontaines](https://en.wikipedia.org/wiki/Château_de_Septfontaines) ★ (MN) | 1783–1784 | – | Villeroy & Boch reception venue | 326 rue de Rollingergrund |

### Ville Haute

| Building | Year | Architect | Use | Address |
|---|---|---|---|---|
| [Hôtel des Postes (main post office building)](https://fr.wikipedia.org/wiki/Hôtel_des_Postes_de_Luxembourg) ★ (MN) | 1908–1910 | Sosthène Weis | POST Luxembourg offices (main post office 1910–2017) | 8A avenue Monterey (corner of rue Aldringen) |
| [Central Bank of Luxembourg (BCL)](https://en.wikipedia.org/wiki/Central_Bank_of_Luxembourg) | – | – | central bank headquarters | 2 boulevard Royal |
| [Refuge Saint-Maximin (Ministry of State)](https://fr.wikipedia.org/wiki/Refuge_Saint-Maximin) | 1751 | Jean-Nicolas Steinmetz | Ministry of State, office of the Prime Minister (since July 2019); Foreign Ministry 1945–2017 | 2 place de Clairefontaine |
| [Hôtel de Bourgogne](https://lb.wikipedia.org/wiki/Hôtel_de_Bourgogne_(Stad_Lëtzebuerg)) | 15th century | – | government building; seat of the Prime Minister 1975–2019 | 4 rue de la Congrégation |
| [Council of State building](https://lb.wikipedia.org/wiki/Staatsrot_(Gebai)) | 1959 (seat since) | – | Council of State (advisory legislative body) | 5 rue Sigefroi |
| [Maison de Cassal](https://lb.wikipedia.org/wiki/Maison_de_Cassal) ★ (MN) | late 16th century | – | government offices (Service des médias, Film Fund) | 5 rue Large |
| [Maison de Raville](https://lb.wikipedia.org/wiki/Maison_de_Raville) ★ (IS) | c. 1575 | – | bank / offices | 4 rue de la Reine |
| [Cité judiciaire](https://lb.wikipedia.org/wiki/Cité_judiciaire) | 2008 | Rob Krier and Léon Krier | law courts and public prosecutor's offices | Plateau du Saint-Esprit |
| [Former National Archives (Saint-Esprit barracks)](https://fr.wikipedia.org/wiki/Archives_nationales_de_Luxembourg) | – | – | National Archives 1968–2026 (moved to Belval in 2026) | 16 plateau du Saint-Esprit |
| [Former Jesuit College / Old Athénée (former National Library)](https://lb.wikipedia.org/wiki/Athénée_de_Luxembourg) ★ (MN) | 17th century | – | former school (Athénée to 1964) and National Library (1973–2019) | 14 rue Notre-Dame / 37 boulevard F.D. Roosevelt |
| [Protestant Church of the Holy Trinity](https://en.wikipedia.org/wiki/Trinity_Church,_Luxembourg) | 17th century (Protestant since 1817) | – | Protestant church | rue de la Congrégation |
| [Royal-Hamilius](https://lb.wikipedia.org/wiki/Royal-Hamilius) | 2019–2020 | Foster + Partners with Tetra Kayser | shops, offices, flats, public squares (Place Émile Hamilius) | boulevard Royal / rue Aldringen / Grand-Rue |
| [Servais House](https://lb.wikipedia.org/wiki/Servais-Haus_(Boulevard_Royal)) ★ (MN) | late 19th century | Pierre Funck | offices | 59 boulevard Royal |
| [Badanstalt (municipal baths)](https://fr.wikipedia.org/wiki/Badanstalt) | – | – | public swimming pool and spa | 12 rue des Bains |
| [Villa Louvigny](https://en.wikipedia.org/wiki/Villa_Louvigny) ★ (MN) | 1936 (present form) | Pierre Reuter, Nicolas Schmit-Noesen, Hubert Schumacher (per Wikidata) | Ministry of Health; RTL (CLT) headquarters for 64 years | 1 allée Marconi (Municipal Park) |
| [Théâtre des Capucins](https://lb.wikipedia.org/wiki/Theaterplaz_(Stad_Lëtzebuerg)) | – | – | municipal theatre | 9 place du Théâtre |
| [Great Synagogue of Luxembourg](https://en.wikipedia.org/wiki/Luxembourg_Synagogue) | 1953 | Victor Engels, René Mailliet, Frantz Kinnen (per Wikidata) | synagogue | 45 avenue Monterey |
| [Luxembourg Stock Exchange](https://en.wikipedia.org/wiki/Luxembourg_Stock_Exchange) | – | – | stock exchange (LuxSE, founded 1928) | 35A boulevard Joseph II |
| [Banque de Luxembourg](https://fr.wikipedia.org/wiki/Banque_de_Luxembourg) | – | – | private bank | boulevard Royal |
| [Fondation Pescatore](https://lb.wikipedia.org/wiki/Fondation_Pescatore) | 1886–1892 | Tony Dutreux | retirement home | 13 avenue J.-P. Pescatore |
| [Glacis Chapel](https://lb.wikipedia.org/wiki/Glaciskapell) ★ (MN) | 1885 | – | Catholic chapel | Place du Glacis (rond-point bd Joseph II / bd de la Foire) |
| [Russian Orthodox Church of Saints Peter and Paul](https://lb.wikipedia.org/wiki/Russesch-orthodox_Kierch_zu_Lëtzebuerg) | 1982 | – | Orthodox church | rue Jean-Pierre Probst |
| [Embassy of France](https://fr.wikipedia.org/wiki/Ambassade_de_France_au_Luxembourg) | – | – | embassy | 8B boulevard Joseph II |
| Embassy of Germany | – | – | embassy | 20–22 avenue Émile Reuter |
| Embassy of United Kingdom | – | – | embassy | 5 boulevard Joseph II |
| Embassy of Switzerland | – | – | embassy | 25A boulevard Royal |

Groupings useful for layers and search:
- **Government and the palace's neighbours**: Refuge Saint-Maximin (Ministry of State since 2019) and Hôtel de Bourgogne (PM's office 1975–2019) behind the cathedral; Council of State on rue Sigefroi; Maison de Raville directly behind the palace; the Chamber of Deputies next to the palace (task 1); Cité judiciaire on the Saint-Esprit plateau. Most ministries occupy old-town houses and offices without landmark value.
- **Finance**: Banque centrale and Banque de Luxembourg on boulevard Royal ("Luxembourg's Wall Street"), Spuerkeess (task 1) and the ARBED building (now Spuerkeess) on avenue de la Liberté, BIL on route d'Esch, the Stock Exchange on boulevard Joseph II, Deutsche Bank (Böhm) and UniCredit (Meier) on Kirchberg.
- **EU**: EIB, Court of Auditors, Eurostat, Jean Monnet 2 (Commission), Alcide De Gasperi and Robert Schuman buildings, ECCL, ESM and the European School on Kirchberg; Publications Office in Gare; Commission buildings also at Cloche d'Or (Ariane, Euroforum, Hitec in OSM). The Court of Justice and Parliament (KAD) are in task 1.
- **Embassy cluster**: villas along boulevard Joseph II, avenue Émile Reuter, rue Marie-Adélaïde, rue des Girondins and boulevard Emmanuel Servais (Belair, Limpertsberg, Ville Haute); the Russian embassy alone in the Château de Beggen.
- **Modernist**: Maternité (Bauhaus, 1936), Alcide De Gasperi tower (1965), Robert Schuman building (1973), Deutsche Bank (Böhm, 1991), UniCredit (Meier, 1993), EIB (Lasdun 1980 / Ingenhoven 2008).
- **Art Nouveau / Belle Époque**: Villa Clivio and Villa Pauly (Mathias Martin), Hôtel des Postes (Sosthène Weis), ARBED (René Théry), Servais house (Pierre Funck), and the protected houses on avenue Pasteur and avenue Victor Hugo in Limpertsberg (see `monuments.csv`).
- **Notable residences**: Maison de Cassal, Maison de Raville, Hôtel de Bourgogne, Servais house, Villa Pauly, Villa Clivio, Villa Louvigny, Château de Septfontaines, Château de Beggen, Mansfeld castle ruins; Robert Schuman's birthplace in Clausen.
- **Abbaye and Kinnekswiss**: Neumünster Abbey is in task 1/2; the Kinnekswiss is the big lawn of the Municipal Park (task 1 park entry; concerts in task 5).

## National protected monuments

**Sources.** (1) The **official INSPIRE dataset** "Protected Sites – Cultural Monuments" (Géoportail / INPA, CC0, data.public.lu, file of 5 Nov 2026) gives cadastral polygons for the whole country under the law of 18 July 1983. For Luxembourg City it has **238 polygons** for **130 distinct monuments**, but only with INPA short codes such as `LUX_GAR_lib_19_MN` (= commune, quarter, street abbreviation, house number, status). Saved as `data/monuments_inpa_polygons.geojson`. (2) The **Luxembourgish Wikipedia lists** "Lëscht vun den nationale Monumenter an der Gemeng Lëtzebuerg/…" (one page per INPA section, maintained from the official INPA list) give the readable version: id, address, coordinates, official name, status history, dates and a Commons photo. Parsed into `data/monuments.csv` / `.geojson` (**397 rows**, including sub-items a/b/c and movable objects).

**Status codes** (`status_now` = last code; `status_history` = sequence): MN = classified national monument (old law, 1983); IS = supplementary inventory (old law); PMN = classification procedure under way; ICPCN / ICMN = procedure to list as national cultural heritage; **PCN = protected national cultural heritage** under the law of 25 Feb 2022, which replaced the MN/IS system. Counts by current status: IS 206, MN 132, PCN 55, ICPCN 3, NM 1.

**By quarter** (point in polygon): Ville Haute 73, Limpertsberg 70, Grund 51, Gare 29, Beggen 26, Hollerich 23, Rollingergrund / Belair-Nord 17, (no usable point) 17, Belair 13, Eich 13, Bonnevoie-Sud 11, Merl 10, Pfaffenthal 9, Clausen 7, Neudorf / Weimershof 6, Hamm 4, Weimerskirch 4, Bonnevoie-Nord / Verlorenkost 3, Kirchberg 3, Dommeldange 2, Cents 2, Gasperich 2, Pulvermuhl 1, Muhlenbach 1.

What is on the list: medieval and Renaissance houses in the Ville Haute and Grund, the fortress remains (Trier front, Vauban steps at the Rham), churches and organs, Belle Époque villas in Gare and Limpertsberg, industrial sites in Hollerich and Dommeldange, and some surprises: the Codex Mariendalensis manuscript, a steam locomotive (CFL 5519) and railway carriages, monumental beeches in Dommeldange, a sweet chestnut in Hamm, a (now felled) copper beech, and post-war buildings (Robert Schuman building, Deutsche Bank, Kirchberg 2025; Saint Pius X church in Belair, procedure opened Sept 2026).

Caveats: many headline landmarks (palace, cathedral, Bock casemates, bridges) do not appear as separate entries in these lists. Why was not checked (other legal protection, ensembles, or gaps in the transcription), so treat absence as unknown, not as unprotected. 14 rows have no coordinates and 3 had obviously wrong ones (dropped). The INPA quarter sections follow cadastral sections and do not exactly match the official quarters, so use the `quarter` column (computed). Official search: the INPA / Institut national pour le patrimoine architectural site (inpa.public.lu) and the Géoportail layer "Patrimoine culturel national".

## Easter-egg ideas (40)

Full stories in `data/easter_eggs.json`. Kinds: curiosity 9, statue 7, street art 4, memorial 3, fountain 3, hidden history 3, famous visitor 2, famous people 2, geography 2, transport 2, legend 1, hidden spot 1, pop culture 1.

- **Melusina, the mermaid wife of Count Siegfried** (49.6118, 6.1370): Legend says Siegfried, who founded the castle on the Bock in 963, married the beautiful Melusina on one condition: he must leave her alone every Saturday.
- **Melusina, 3D-printed** (49.6109, 6.1360): Serge Ecker's Melusina statue on the left bank of the Alzette in the Grund, facing Saint-Jean, won a competition for the city's 1,050th anniversary and was made with a large 3D printer.
- **The 'Hollow Tooth' is a fake ruin** (49.6120, 6.1377): The ruined tower on the Bock (Huelen Zant / Dent creuse) is not part of Siegfried's castle.
- **The monument that never was** (49.6118, 6.1376): Luxembourg's very first public monument was meant to honour John the Blind, Count of Luxembourg and King of Bohemia (1296–1346).
- **Goethe slept here (twice)** (49.6116, 6.1355): In 1792 Goethe came through the fortress city with Duke Carl August of Saxe-Weimar during the war against revolutionary France.
- **Victor Hugo in the park** (49.6107, 6.1238): Victor Hugo visited Luxembourg City in 1862, 1863 and 1864, and spent two and a half months in exile at Vianden in 1871.
- **Father of Europe, born in Clausen** (49.6158, 6.1430): Robert Schuman, whose declaration of 9 May 1950 launched the European Coal and Steel Community, was born on 29 June 1886 in the Clausen faubourg.
- **A monument opened on bridge day** (49.6172, 6.1291): The Robert Schuman monument by the Red Bridge was inaugurated on 24 October 1966, the same day as the bridge and the Alcide De Gasperi tower across the valley.
- **The Golden Lady who went missing** (49.6094, 6.1289): The Gëlle Fra (Claus Cito, 1923) was torn down by the Nazis in 1940.
- **The sheep fountain (and the hidden sculptor)** (49.6119, 6.1312): The Hämmelsmarsch fountain (Wil Lofy, 1981–82) shows four musicians, five sheep and two children in the folk parade that announces a village fair.
- **The Red Well and its punishment wheel** (49.6119, 6.1312): Around 1740 a 64 m shaft was blasted into the sandstone to supply the fortress with water.
- **Grand Duchess Charlotte** (49.6099, 6.1325): The bronze of Grand Duchess Charlotte (reigned 1919–1964), symbol of resistance during her wartime exile, is by Jean Cardot of the Institut de France.
- **Why the square is called 'Knot'** (49.6107, 6.1313): Place Guillaume II is known as the Knuedler after the knotted rope belts of the Franciscan friars whose friary stood there.
- **Where the national motto comes from** (49.6113, 6.1286): The Dicks-Lentz monument (architect Georges Traus, sculptures by Pierre Federspiel) honours the poets Edmond de la Fontaine ('Dicks') and Michel Lentz.
- **Péiter Onrou, the statue in the rock** (49.6194, 6.1301): A life-size statue sits in a grotto in the Crispinus rock on the Eecher Bierg, reached by steps from rue des Glacis.
- **Kaddish** (49.6090, 6.1317): The Shoah memorial by Shelomo Selinger, of pink Breton granite, was unveiled on 17 June 2018 between the cathedral and the former Sainte-Sophie convent.
- **The eternal flame on Cannon Hill** (49.6071, 6.1342): The Kanounenhiwwel ('cannon hill') on the Saint-Esprit plateau was heaped up from the rubble of the old Saint-Esprit barracks.
- **A house of cards made of steel** (49.6353, 6.1767): Richard Serra's 'Exchange' (1996) on the Rond-point Serra at Kirchberg is made of seven Cor-Ten steel plates, 20.2 m tall and 33 tonnes each, leaning against each other like a house of cards.
- **Walk through the sculpture** (49.6152, 6.1291): Jean-Bernard Métais's 'Le Passe-muraille' in the park in front of the Fondation Pescatore is two pierced bronze quarter-spheres, 6 m across, with a narrow passage between them that you can walk into.
- **Trees planted for princes** (49.6159, 6.1288): A horse chestnut in the Pescatore park was planted for the birth of Prince Jean (later Grand Duke) on 5 January 1921; around 2000 it was 23 m tall.
- **A tree that was a national monument** (49.6104, 6.1339): A copper beech in the courtyard of the City History Museum (rue du Saint-Esprit) was itself a protected national monument from 1989.
- **Gandhi without his glasses** (49.6102, 6.1218): The bronze bust of Mahatma Gandhi by Amar Nath Sehgal in the Municipal Park (1973) is one of the few portraits of him without his round spectacles.
- **Fire-eaters on the theatre square** (49.6128, 6.1307): Bénédicte Weis's bronze 'Saltimbanques' (1987), with a fire-eater and dancers, won the city's 1986 sculpture competition for place du Théâtre, in front of the Capucins theatre.
- **Ten doves of peace** (49.6076, 6.1351): On the Saint-Esprit plateau a granite block carries a bronze arc of ten doves by Fabrizio Cocchia (1986), tracing a bird's flight as it skims the water.
- **A fountain for a birdwatcher** (49.6181, 6.1258): The Xavier Brasseur fountain (1922–1926, Nicolas Petit and Albert Kratzenberg) is set into the wall of the Lycée Robert-Schuman.
- **The ivy-covered king** (49.6026, 6.1361): 'Ubu roi' (1995) by the architects Hermann & Valentiny is a steel cone almost 4 m tall with two wing-like arms, completely overgrown with ivy, at the junction of rue de Bonnevoie and rue du Laboratoire.
- **Eurovision in the park** (49.6112, 6.1226): The Eurovision Song Contest was held twice (1962 and 1966) in the Villa Louvigny in the Municipal Park, then home of Radio-Télé-Luxembourg.
- **A steel company with a bowling alley** (49.6057, 6.1301): When the ARBED headquarters opened on avenue de la Liberté in the 1920s, it had smoking rooms, a ballroom, a library, a gym and a bowling alley for its staff.
- **The Gestapo villa** (49.6061, 6.1250): During the Nazi occupation the Gestapo ran its headquarters from the Villa Pauly on boulevard de la Pétrusse.
- **General Patton among his men** (49.6117, 6.1857): General George S.
- **Born before the opening** (49.6174, 6.0986): The first baby was born at the Bauhaus-style Maternité Grande-Duchesse Charlotte on 4 March 1936, six days before the hospital was officially opened.
- **Luxembourg's first concrete building** (49.6163, 6.1278): The Fondation Pescatore retirement home (1886–1892), which looks like a château, was the first building in Luxembourg to use reinforced concrete.
- **The lowest point in the capital** (49.6440, 6.1310): The city's lowest point, 232 m above sea level, is on rue de Bastogne in Beggen in the Alzette valley.
- **A tram without wires** (49.6109, 6.1262): Through the city centre, between the Red Bridge and the station (3.6 km), the T1 tram runs without overhead wires, on power stored in supercapacitors, so no cables clutter the historic streets.
- **Free rides for everyone** (49.5997, 6.1333): Since 29 February 2020 all buses, trams and trains in Luxembourg have been free for everyone: the first country in the world to do this nationwide.
- **36 steam engines in two round sheds** (49.6014, 6.1365): Each of the two Rotondes in Bonnevoie (1877, 52 m across) had room for 18 steam locomotives around a turntable.
- **The 'golden bell' was a hotel** (49.5828, 6.1252): The Cloche d'Or district takes its name from a 1937 hotel on the old Esch road, with a restaurant, bowling alley and outdoor pool.
- **The Prime Minister worked in the old mint** (49.6096, 6.1321): The Hôtel de Bourgogne held the mint in the 15th century and was home to Charles the Bold's deputy governor.
- **A steam engine is a national monument** (49.5997, 6.1333): The national protected list includes not only buildings but trains: CFL steam locomotive 5519, diesel-electric locomotive 1604, a twin railcar Z 208/218 and ten Wegmann carriages are all listed (kept by the railways near the main station).
- **A city of 3.55 km²** (49.6113, 6.1291): Until the communes of Eich, Hamm, Hollerich and Rollingergrund were merged into it in 1920, the city proper covered only 3.55 km².

Ideas for using them: Melusina's tail flicking in the Alzette near the Bock at night; a tiny figure of Goethe on the Bock; the Gëlle Fra briefly gone from her column with a hint pointing to the Josy Barthel stadium; the Hämmelsmarsch sheep wandering off the fountain; a soldier on the Roude Pëtz treadwheel in fortress mode (task 4); Patton's grave in Hamm; 18 steam engines visible inside a Rotonde; the tram losing its overhead wires at the Red Bridge.

## Images (14)

| File | Subject | Shows | Licence |
|---|---|---|---|
| [`hotel-des-postes__exterior.jpg`](images/hotel-des-postes__exterior.jpg) | Hôtel des Postes | Neo-Renaissance post office building, rue Aldringen / avenue Monterey | CC BY-SA 4.0 |
| [`arbed-building__facade.jpg`](images/arbed-building__facade.jpg) | ARBED building (19 Liberté) | Façade of the former ARBED headquarters on avenue de la Liberté | CC BY-SA 3.0 |
| [`villa-pauly__exterior.jpg`](images/villa-pauly__exterior.jpg) | Villa Pauly | The villa on boulevard de la Pétrusse | CC BY-SA 2.5 |
| [`villa-clivio__exterior.jpg`](images/villa-clivio__exterior.jpg) | Villa Clivio | Art Nouveau villa at 17 rue Goethe | CC BY-SA 3.0 |
| [`rotondes__south-roundhouse.jpg`](images/rotondes__south-roundhouse.jpg) | Rotondes | The southern railway roundhouse in Bonnevoie | CC BY-SA 3.0 |
| [`alcide-de-gasperi__tower.jpg`](images/alcide-de-gasperi__tower.jpg) | Alcide De Gasperi building | Kirchberg's first high-rise on place de l'Europe | CC BY-SA 3.0 |
| [`chateau-septfontaines__exterior.jpg`](images/chateau-septfontaines__exterior.jpg) | Château de Septfontaines | The Boch family's château in Rollingergrund | CC0 |
| [`maternite__exterior.jpg`](images/maternite__exterior.jpg) | CHL Maternité | Bauhaus-style maternity hospital (1936) | CC BY-SA 4.0 |
| [`villa-louvigny__exterior.jpg`](images/villa-louvigny__exterior.jpg) | Villa Louvigny | Former RTL headquarters in the Municipal Park | CC BY-SA 3.0 |
| [`hotel-saint-maximin__exterior.jpg`](images/hotel-saint-maximin__exterior.jpg) | Refuge Saint-Maximin (Ministry of State) | Baroque refuge on place de Clairefontaine | CC BY-SA 3.0 |
| [`quarter-clausen__view.jpg`](images/quarter-clausen__view.jpg) | Clausen (quarter) | View over the Clausen quarter | CC BY-SA 4.0 |
| [`quarter-belair__aerial.jpg`](images/quarter-belair__aerial.jpg) | Belair (quarter) | Aerial view of the Belair quarter | CC BY-SA 4.0 |
| [`quarter-gasperich__ban-de-gasperich-aerial.jpg`](images/quarter-gasperich__ban-de-gasperich-aerial.jpg) | Gasperich / Ban de Gasperich (quarter) | Aerial view of the Ban de Gasperich development in May 2018 | CC BY-SA 4.0 |
| [`quarter-pfaffenthal__red-bridge.jpg`](images/quarter-pfaffenthal__red-bridge.jpg) | Pfaffenthal (quarter) | Pfaffenthal in the valley under the Red Bridge | CC BY-SA 4.0 |

Not downloaded on purpose: recent sculptures and buildings whose authors are alive or died less than 70 years ago (Melusina by Serge Ecker, Charlotte statue by Jean Cardot, Hämmelsmarsch by Wil Lofy, Serra's Exchange), because Luxembourg has no freedom of panorama and Commons copies may be deleted (see task 1). Many more photos of protected buildings are linked in the `commons_image` column of `monuments.csv`.

## Gaps

- **"Grénge Mann" and "Schëtzebuerg"**: no source found for either as a Luxembourg City legend or place (searched lb/en/fr Wikipedia), so they are left out rather than guessed. Ask a local source (e.g. the Lëtzebuerg City Museum, or *Luxemburger Sagen* by N. Gredt) before using them.
- **Population by STATEC** (1 Jan 2026 commune figure) was not fetched; the city's own register figure is used everywhere. Quarter figures are only published by the city.
- **Twin cities, city flag colours**: the city's "Networks and partnerships" page returned HTTP 403; values come from Wikipedia.
- **Years and architects** are missing for ~25 buildings (mostly corporate and EU offices: ECA, Eurostat, ECCL, Bourse, BIL, Banque centrale's building, Chamber of Commerce, ESM). Wikidata has little building-level data for Luxembourg.
- **Jean Monnet 2**: location approximate; completion date not confirmed.
- **Wikidata SPARQL** was rate-limited (outage rule, 1 request/min) during the run, so the Wikidata data comes from entities linked from OSM (649 items) through the Wikidata API instead of a full SPARQL query.
- **Monument list**: the lb Wikipedia transcription can lag the official INPA list by weeks; the INSPIRE polygons are official but use short codes only.
- **Quarter landmarks** for small outer quarters (Muhlenbach, Weimerskirch, Cents) are thin; they have few notable buildings.

## Sources (accessed 6 Nov 2026)

- Ville de Luxembourg, *Facts and figures*: area, land use, elevation range, population 31 Dec 2025, staff (1 Jan 2026), bus fleet. https://www.vdl.lu/en/city/a-glance/facts-and-figures
- Ville de Luxembourg, *État de la population au 31.12.2025* (PDF, 64 pp.): totals, nationalities, population by quarter. https://www.vdl.lu/sites/default/files/media/ni/document/Etat%20de%20la%20population%202025.pdf
- Ville de Luxembourg open data, *Quartiers de la Ville de Luxembourg* (CC BY, data.public.lu dataset 64104e9bb4d7e0b4060d266d): https://maps.vdl.lu/arcgis/rest/services/OPENDATA/GEOJSON/FeatureServer/24 ; fountains: same service, layer 2.
- Géoportail / INPA, *INSPIRE Annex I – Protected Sites – Cultural Monuments* (CC0, file of 5 Nov 2026): https://data.public.lu/datasets/5d00d7440f7fb07999ed1c46
- lb Wikipedia, *Lëscht vun den nationale Monumenter an der Gemeng Lëtzebuerg* (21 quarter subpages, revisions as of Nov 2026) and many building articles (Arbedsgebai, Postgebai, Cité judiciaire, Villa Pauly, Refuge Sankt Maximin, Hôtel de Bourgogne, Rotonden, Alcide-De-Gasperi-Gebai, Jean-Monnet-2-Gebai, Infinity, Stadion vu Lëtzebuerg, CHL Maternité, Gëlle Fra, Roude Pëtz, Huelen Zant, Hämmelsmarsch-Buer, Melusina, Goethe, Victor Hugo…).
- en/fr Wikipedia: *Luxembourg City* (mayor, council, twin towns, transport, UNESCO), *Tramway de Luxembourg* (T1 history and stops), *Lydie Polfer*, *Luxembourg (ville)* (coat of arms).
- OpenStreetMap via Overpass (ODbL): building and amenity names, embassy locations, the T1 route relation, wikidata tags; the project's own extract `data/raw/osm/places.json` for addresses.
- Wikidata (wbgetentities API): inception, architect, heritage and sitelinks for 649 items linked from OSM.
- Wikimedia Commons: images, see `sources.json`.

## Findel

Facts behind the aircraft over the map (PLAN_NEXT.md item 11; `pipeline/build_flights.py`,
`pipeline/build_plane_sprites.py`, `web/src/sky/flights.ts`).

- **Runway 06/24:** one runway, 4000 m by 60 m, asphalt, from OpenStreetMap (`aeroway=runway`, `ref=06/24`, fetched
  through Overpass on 8 Nov 2026 and kept in `data/raw/osm/runway.json`). Ends at 49.6175 N 6.1875 E (threshold 06)
  and 49.6354 N 6.2356 E (threshold 24). In the map's grid it points 060 / 240 degrees. Field elevation used: 376 m.
  The 06 threshold projects to about `21524,10535`, inside the map's frame but outside the painted area.
- **Fleets** (Wikipedia, "Luxair", fleet table as of July 2026): Luxair flies Boeing 737-700, 737-800 and 737 MAX 8,
  De Havilland Canada Dash 8-400 and, since December 2025, Embraer E195-E2 (E190-E2 and 737 MAX 10 on order).
  Cargolux flies Boeing 747-8F and 747-400F; only the 747-8F is modelled.
- **Sizes used for the models:** 747-8F 76.3 m long, 68.4 m span; 737-800 39.5 m, 35.8 m with winglets; E195-E2
  41.5 m, 35.1 m; Dash 8-400 32.8 m, 28.4 m (manufacturers' published figures).
- **Liveries:** simplified on purpose, without logos or lettering: Cargolux white with a blue fin and a red band;
  Luxair white with a light-blue fin, winglets and engine lips. They follow the owner's brief, not reference photos;
  the owner checks them by eye.
- **Procedures and schedule:** not the published ones. Departures 24 climb at 7 % to 3000 ft and turn north or south;
  arrivals 06 fly a 3 degree final over the city; arrivals 24 cross north of the city on a downwind at 3500 ft; the
  runway changes to 06 when the tailwind on 24 is over 2.5 m/s. Luxair: 40 departures and 40 arrivals from 06:00 to
  23:00; Cargolux: 12 movements, most in the evening, at most 4 between 23:00 and 06:00 (a simplification of the
  airport's night rules, which were not checked against the AIP).
