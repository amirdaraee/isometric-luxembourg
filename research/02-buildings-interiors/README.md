# 02 – Famous buildings: interiors, plans and 3D

Reference material for an "explore inside" feature: for 22 buildings of Luxembourg City, the facts that matter for a 3D or interior view (architects, dates, style, floors, rooms, materials, colours, access), 71 freely licensed interior photos, plan and section sources, and 3D / 360° tour links. Exterior photos are in `../01-landmarks/` and are not repeated here; tunnels and casemates are covered in depth by task 3.

How to use this folder:
- `images/<slug>__<what>.jpg`: ~1600 px wide thumbnails from Wikimedia Commons (smaller if the original is smaller). Slugs match `01-landmarks` where the building is there too.
- `sources.json`: one record per file with `building`, `shows`, `source_page`, `author`, `licence`, `licence_url`. All files are public domain, CC0, CC BY or CC BY-SA (licences as stated on Commons, November 2026). **CC BY / CC BY-SA files need attribution if they, or close traces of them, are published; CC BY-SA derivatives must be shared alike.** Used as drawing reference only, they leave no trace.
- Plans: only one plan could be downloaded (a public-domain 17th-century Jesuit drawing). Every other plan, section or seating map is copyrighted and is listed as a **link only**, with what it shows.

**Freedom of panorama caveat.** Luxembourg has no freedom-of-panorama exception, and Commons treats interiors of recent buildings as copyrighted works of the architect (architect alive or dead less than 70 years). So interiors of the Philharmonie (Portzamparc), Mudam (Pei, d. 2019), the Court of Justice (Perrault), the BnL (Bolles+Wilson), the Grand Théâtre (Bourbonnais, d. 1988), the 2010 Villa Vauban wing and the modern parts of the MNHA and City Museum are thin on Commons, and files there now may be deleted later. For these, the architects' and institutions' own photos (link only) and the 360° tours are the main references.

## Best documented for "explore inside"

| Rank | Building | Why |
|---|---|---|
| 1 | **Notre-Dame Cathedral + crypt** | 9 photos (nave, choir, vault, organ gallery, glass, 4 of the crypt), 89+ more on Commons, official 360° tour, free entry every day. Old fabric, so no copyright issues. |
| 2 | **Chamber of Deputies** | Commons has a 72-file interior category: plenary hall from every side, staircase, corridors, committee rooms, bar. Visits on request and on heritage days. |
| 3 | **Court of Justice of the EU** | Both main courtrooms (gold mesh ceiling), entrance hall, gallery and an **architectural model of the whole complex**; official 360° tour; Perrault publishes plans. |
| 4 | **Philharmonie** | Both halls, organ and foyer on Commons; official seating maps for both halls; 360° tour; published plan and section (Steeldoc PDF). |
| 5 | **Cercle Cité** | CC0 series of the ballroom, stained-glass dome, galleries and landings. Open free for exhibitions. |
| 6 | **Gare Centrale** | Main hall, painted ceiling, the city-silhouette stained-glass window and the modern glass passage. Open all day. |
| 7 | **BnL (National Library)** | Reading room under the timber roof from several angles; architects publish ground plan and section. Free entry. |
| 8 | Saint-Michel, Saint-Jean du Grund, Villa Vauban | Good wide shots of the main spaces; small, simple plans that are easy to model. |
| – | Weak | Hôtel de Ville (no free interior at all), Grand Théâtre (foyer only), Casino Luxembourg (one stair), Natur Musée (one room), Neimënster (chapel only), City Museum (two rooms), Spuerkeess (bank museum only, no banking hall), Grand Ducal Palace (3 photos; no photography allowed on tours). |

### 3D models and virtual tours found

- **Official 360° tours (Luxembourg City Tourist Office)**, index: https://luxembourg-city.com/en/attractions/360-views. Each place page has a "Show the 360° view" button. Relevant here: Cathedral, Bock casemates, Archaeological crypt (Bock), European Court of Justice, Lëtzebuerg City Museum, Mudam, Musée Dräi Eechelen, Nationalmusée um Fëschmaart, Neimënster, Philharmonie (links in each section). Not freely licensed; reference only.
- **MNAHA on Sketchfab** (https://sketchfab.com/mnaha): museum objects and **Fort Louvigny** (CC BY, downloadable): https://sketchfab.com/3d-models/4b2cf11b951149299f170dd139665908. The MNAHA's fortress documentation centre (CDF) also made 3D scans of the Fort Thüngen casemates and the Olizy/Niedergrünewald galleries in 2018; they are presented at https://collections.mnaha.lu/stories/casemates and one is on Europeana as glTF: https://www.europeana.eu/item/1130/share3d_1557 (check licence per item). Relevant to task 3.
- **Natur Musée (mnhnl) on Sketchfab** (https://sketchfab.com/mnhnl): specimens and local sandstone/tree scans (many CC BY), plus "Door from 1823 Grund Luxembourg" (no licence shown): https://sketchfab.com/3d-models/b2367009862c4ffd8f8cc78216917af0. Not building models.
- **No free 3D model was found** on Sketchfab (API search, November 2026) for the cathedral, palace, Philharmonie, Mudam, Court of Justice or any other building in this list; Wikimedia Commons has no 3D (STL) files for them either. The CJEU architectural model photo (`cjeu__architectural-model.jpg`) and the 01-landmarks aerials are the best massing references.
- The Nationalmusée is said to offer immersive 3D tours (listed on https://museumforall.eu/museum/luxembourg-national-museum-of-history-and-art-mnha/); not verified.

## Index

[Notre-Dame Cathedral](#cathedral) · [Grand Ducal Palace](#grand-ducal-palace) · [Chamber of Deputies](#chamber-of-deputies) · [Hôtel de Ville](#hotel-de-ville) · [Cercle Cité](#cercle-cite) · [Philharmonie](#philharmonie) · [Grand Théâtre](#grand-theatre) · [Mudam](#mudam) · [Nationalmusée um Fëschmaart (MNHA)](#mnha) · [Lëtzebuerg City Museum](#city-museum) · [Villa Vauban](#villa-vauban) · [Natur Musée](#natur-musee) · [Neimënster Abbey](#neumunster-abbey) · [Saint-Michel](#saint-michel) · [Saint-Jean du Grund](#saint-jean-grund) · [Casino Luxembourg](#casino-luxembourg) · [Gare Centrale](#gare-centrale) · [Court of Justice of the EU](#cjeu) · [Fort Thüngen / Dräi Eechelen](#drai-eechelen) · [Spuerkeess](#spuerkeess) · [National Library (BnL)](#bnl-kirchberg) · [Bock casemates](#bock-casemates)

## Old town (Ville Haute)

<a id="cathedral"></a>
### Notre-Dame Cathedral (Cathédrale Notre-Dame)

| | |
|---|---|
| Architects | Jesuit church begun 1613 (Jean du Blocq is usually credited with the design; Ulrich Job of Lucerne built it); carved organ gallery and portal by Daniel Muller (d. 1623). East extension 1935–38 by Hubert Schumacher. |
| Dates | First stone 7 May 1613, consecrated 17 Oct 1621 as the Jesuit college church; cathedral since 1870; enlarged eastwards 1935–38 (new transept, choir, east towers, crypt); west tower burned 1985 and was rebuilt. |
| Style | Late Gothic structure ("Jesuit Gothic") with Renaissance and Baroque ornament; the 1930s extension continues it in a sober historicist style. |
| Layout | Three-aisled hall church (aisles nearly as high as the nave) with galleries over the aisles in the old part; transept and long choir from 1935–38; three towers (old west tower, two slim east spires). Crypt under the 1930s choir. |
| Main spaces | **Nave**: pale sandstone clustered piers carrying painted net/star rib vaults, Renaissance-carved gallery balustrades. **Organ gallery** (west): richly carved by Daniel Muller. **Choir**: tall stained-glass windows (mostly 20th c.), high altar. **Chapel of the Consolatrix Afflictorum**: the miraculous Virgin, focus of the Octave pilgrimage. **Crypt** (1930s): low hall on squat columns; the **grand-ducal burial vault** closed by a bronze gate guarded by two lions (sculptor Auguste Trémont); the **tomb of John the Blind**, King of Bohemia and Count of Luxembourg (d. 1346), with its sculpted mourners (remains moved here in 1945); bishops' tombstones; a small modern crypt chapel. |
| Materials, colours | Warm yellow-grey sandstone, white/cream plastered vault cells with painted ribs and ornament, dark oak furnishings, deep blue/red stained glass; crypt in grey stone with blue-tiled and starry details. |
| Access | Open daily, free (Mon–Sat 08:00–18:00, Sun 09:00–19:00, per the tourist office). Crypt usually accessible; closed during services. |
| Official site | https://www.cathol.lu/ (archdiocese) · tourist page https://luxembourg-city.com/en/place/church/cathedral-of-the-blessed-virgin |
| Wikipedia | [en: Notre-Dame Cathedral, Luxembourg](https://en.wikipedia.org/wiki/Notre-Dame_Cathedral,_Luxembourg) |

Images:
- [`cathedral__nave.jpg`](images/cathedral__nave.jpg): Nave looking east to the choir: clustered sandstone piers and rib vaults (CC0, Helmlechner)
- [`cathedral__choir-windows.jpg`](images/cathedral__choir-windows.jpg): Choir with its tall stained-glass windows and high altar (CC BY-SA 2.0, Diego Tirira from Quito, Ecuador)
- [`cathedral__vault-ceiling.jpg`](images/cathedral__vault-ceiling.jpg): Looking straight up into the painted late-Gothic star/net rib vault (CC BY-SA 4.0, Diego Delso)
- [`cathedral__organ-gallery.jpg`](images/cathedral__organ-gallery.jpg): West organ gallery with carved Renaissance balustrade (Daniel Muller) (CC BY-SA 2.0, Diego Tirira from Quito, Ecuador)
- [`cathedral__stained-glass.jpg`](images/cathedral__stained-glass.jpg): Stained-glass windows, detail of figures and colours (CC BY-SA 3.0, Pudelek (Marcin Szala))
- [`cathedral__crypt-hall.jpg`](images/cathedral__crypt-hall.jpg): Crypt hall (1930s) with columns, looking towards the bronze grille of the grand-ducal vault (CC BY 3.0, Dguendel)
- [`cathedral__crypt-vault-gate.jpg`](images/cathedral__crypt-vault-gate.jpg): Entrance to the grand-ducal burial vault: bronze gate flanked by two lions (CC BY-SA 4.0, User:Pietz)
- [`cathedral__crypt-tomb-john-the-blind.jpg`](images/cathedral__crypt-tomb-john-the-blind.jpg): Tomb of John the Blind, King of Bohemia, in the crypt (CC BY-SA 4.0, Dudva)
- [`cathedral__crypt-chapel.jpg`](images/cathedral__crypt-chapel.jpg): Crypt chapel with red chairs and starry-tiled vault (CC BY 3.0, Dguendel)
- [`cathedral__plan-jesuit-college-project.jpg`](images/cathedral__plan-jesuit-college-project.jpg): 17th-c. Jesuit plan (unexecuted variant) of the ground floor of the Jesuit college of Luxembourg, whose church became the cathedral (BnF, Jesuit plans collection) (Public domain, Unknown Jesuit draughtsman (17th c.); Bibliothèque nationale)

Plans and sections:
- Downloaded: `cathedral__plan-jesuit-college-project.jpg`, a 17th-century **unexecuted variant** of the ground floor of the Jesuit college of Luxembourg (BnF, Jesuit plans collection; public domain). Shows how the college buildings were planned around the church; not the as-built cathedral. More sheets of the same series (refused project, upper floors): https://commons.wikimedia.org/w/index.php?search=%22Coll%C3%A8ge+de+Luxembourg%22&ns6=1
- No modern floor plan of the cathedral was found on Commons. The cathedral's footprint can be traced from OSM / the cadastre (geoportail.lu) and the 01-landmarks aerials.

3D / virtual tour: official 360° tour on the tourist-office page above. More interior photos: https://commons.wikimedia.org/wiki/Category:Interior_of_Cath%C3%A9drale_Notre-Dame_de_Luxembourg and https://commons.wikimedia.org/wiki/Category:Church_windows_of_Cath%C3%A9drale_Notre-Dame_de_Luxembourg

<a id="grand-ducal-palace"></a>
### Grand Ducal Palace (Palais grand-ducal)

| | |
|---|---|
| Architects | Original city hall 1572 (Renaissance façade); 1741 extension; 1890s renovation and new wing by Gédéon Bordiau (Belgian) and Charles Arendt (state architect). |
| Dates | City hall 1572–1795; prefecture 1795, seat of government 1817, governor's residence; grand-ducal residence since 1890; interior renovated 1883; looted under Nazi occupation (used as concert hall and tavern); redecorated in the 1960s; thoroughly restored 1991–96. |
| Style | Flemish/Spanish-influenced Renaissance façade with dense geometric carving; interiors 19th-century historicist (Louis XV/XVI revival, white and gold). |
| Floors | Ground floor (entrance, guard), **first floor = state rooms (piano nobile)**, upper floors with apartments; a 19th-century gangway links it to the Chamber of Deputies next door. |
| Main rooms (summer tour route) | **Grand staircase** linking the state rooms. **Dining room** (state banquets): Napoleon-given tapestries, bronze and crystal chandeliers, ceiling with the arms of the twelve cantons. **King's Room / King's Lounge**: dark panelling, painted ceiling. **Map room**. **Reception hall / Ballroom**: white and gold, mirrors, chandeliers, balcony over the street. **Yellow Room** (the Grand Duke's Christmas message is filmed here). **Grand Duke's study**, and two private apartment areas at the end of the tour. |
| Materials, colours | Honey-coloured sandstone outside; inside white panelling with gilt mouldings, yellow and red silk, parquet, crystal chandeliers, tapestries. |
| Access | Guided tours only, in summer (2026: 18 July – 30 August, about 75 min, FR/EN/DE/LB, adults €18). Tickets from the Luxembourg City Tourist Office. **No photography inside.** Lift access. Also open on European Heritage Days. |
| Official site | https://monarchie.lu/en/visit-grand-ducal-palace |
| Wikipedia | [en: Grand Ducal Palace, Luxembourg](https://en.wikipedia.org/wiki/Grand_Ducal_Palace,_Luxembourg) |

Images:
- [`grand-ducal-palace__ballroom.jpg`](images/grand-ducal-palace__ballroom.jpg): Ballroom: white and gold panelling, mirrors, chandeliers (CC BY-SA 4.0, MrSkylarMan)
- [`grand-ducal-palace__kings-lounge.jpg`](images/grand-ducal-palace__kings-lounge.jpg): King's Lounge: painted ceiling, dark panelling, red carpet (CC BY-SA 4.0, MrSkylarMan)
- [`grand-ducal-palace__state-salon.jpg`](images/grand-ducal-palace__state-salon.jpg): White-and-gold state salon used for audiences (people in frame) (Public domain, Office of U.S. House Speaker)

Plans: none public. Room order is given in the tour descriptions: https://chronicle.lu/category/at-home/55939-grand-ducal-palace-welcomes-chronicle-lu-for-a-tour-of-the-royal-residence (link only; press photos of the rooms) and https://en.paperjam.lu/article/visiting-the-grand-ducal-palace-a-journey-to-the-heart-of-luxembourg.

3D / virtual tour: none found (no 360° tour on the tourist-office list). Only 11 interior files on Commons, mostly official visits: https://commons.wikimedia.org/wiki/Category:Interiors_of_Grand_Ducal_Palace_(Luxembourg)

<a id="chamber-of-deputies"></a>
### Chamber of Deputies (Hôtel de la Chambre des Députés)

| | |
|---|---|
| Architect | Antoine Hartmann. Later annexes in the neighbouring buildings along the Rue du Marché-aux-Herbes and Rue de l'Eau. |
| Dates | Built 1858–60 next to the palace (to which it is linked by a gangway); renovated several times; during the Covid-19 pandemic (2020–21) the Chamber met in the Cercle Cité for distancing. |
| Style | Neo-Renaissance, harmonised with the palace. |
| Main rooms | **Plenary hall**: horseshoe of oak desks on red carpet facing the president's raised desk and tribune; tall windows with heavy curtains, faux-marble pilasters, crystal chandeliers, coffered ceiling with skylight, a public gallery on three sides with a carved balustrade. **Grand staircase** with red carpet and carved wooden balustrade. Committee rooms, corridors and a modern glass link, a members' bar, attic meeting rooms (all shown in the Commons category below). |
| Materials, colours | Warm wood, red and gold textiles, cream walls, marbled columns. |
| Access | Public sessions can be watched from the gallery; free guided visits for groups on request, and open days (European Heritage Days, e.g. 17 Oct 2026). |
| Official site | https://www.chd.lu/ |
| Wikipedia | [en: Hôtel de la Chambre](https://en.wikipedia.org/wiki/H%C3%B4tel_de_la_Chambre) |

Images:
- [`chamber-of-deputies__plenary-hall.jpg`](images/chamber-of-deputies__plenary-hall.jpg): Plenary hall seen from the public gallery: horseshoe of desks, chandeliers, marble pilasters (CC BY-SA 3.0, GilPe)
- [`chamber-of-deputies__plenary-in-session.jpg`](images/chamber-of-deputies__plenary-in-session.jpg): Plenary hall in session, view along the benches (CC BY-SA 2.0, oscepa)
- [`chamber-of-deputies__plenary-presidium.jpg`](images/chamber-of-deputies__plenary-presidium.jpg): President's desk and tribune at the head of the plenary hall (CC BY-SA 3.0, GilPe)
- [`chamber-of-deputies__staircase.jpg`](images/chamber-of-deputies__staircase.jpg): Main staircase with red carpet and carved balustrade (CC BY-SA 3.0, GilPe)

Plans: the Chamber publishes a seating plan of the deputies (hemicycle) on chd.lu (link only, changes each legislature). No architectural plan found.

3D / virtual tour: none found. More photos (72 files): https://commons.wikimedia.org/wiki/Category:Interior_of_H%C3%B4tel_de_la_Chambre_des_d%C3%A9put%C3%A9s

<a id="hotel-de-ville"></a>
### Hôtel de Ville (City Hall)

| | |
|---|---|
| Architect | Justin Remont (Liège). Bronze lions on the steps by Auguste Trémont (1930s). |
| Dates | Built 1830–38 on the site of the former Franciscan friary on Place Guillaume II (Knuedler). |
| Style | Neoclassical; two main storeys over a raised ground floor, cream render and sandstone dressings, hipped slate roof. |
| Main rooms | Council chamber (municipal council meetings), reception hall / salle des fêtes on the first floor used for civil weddings and official receptions, mayor's offices. |
| Access | Not open to visitors; public council meetings; weddings; occasional open days. |
| Official site | https://www.vdl.lu/ |
| Wikipedia | [en: City Hall, Luxembourg](https://en.wikipedia.org/wiki/City_Hall,_Luxembourg) |

Images: **no freely licensed interior photo exists on Commons** (the category has 53 files, all exteriors, details or historic views; see `../01-landmarks/` for exteriors).

Plans / 3D: none found.

<a id="cercle-cite"></a>
### Cercle Cité (Cercle municipal)

| | |
|---|---|
| Architects | Pierre Funck and his son Paul Funck (competition launched 1902, won 1904). Annex "Cité" (library, conference centre) added 2011, linked behind. |
| Dates | Built 1904–09 (some sources say 1904–05 for the shell); municipal palace from Sept 1909, inaugurated 1910; renovated and reopened as "Cercle Cité" in 2011. |
| Style | Neo-Baroque / Belle Époque, with a sculpted frieze (Countess Ermesinde granting the city charter) and a clock pediment on Place d'Armes. |
| Main rooms | **Grande Salle** (ballroom): parquet, white stucco, mirrors, red curtains, chandeliers; used for receptions, concerts, the Chamber's sessions during its renovation. **Stair hall** under an oval **stained-glass dome**. **Vaulted gallery / foyer** with marble floor and a central glazed bay. Reception salons; the **Ratskeller** exhibition space (basement, free); conference rooms on the upper floor of the annex. |
| Materials, colours | Golden sandstone outside; inside white and cream stucco, marble, polished parquet, gilt details, coloured glass. |
| Access | Ratskeller exhibitions free, daily; the reception rooms on open days and events. |
| Official site | https://cerclecite.lu/ |
| Wikipedia | [en: Cercle Municipal](https://en.wikipedia.org/wiki/Cercle_Municipal) |

Images:
- [`cercle-cite__ballroom.jpg`](images/cercle-cite__ballroom.jpg): Grande Salle (ballroom): parquet, white stucco, red curtains (CC0, Procrastineur49)
- [`cercle-cite__glass-dome.jpg`](images/cercle-cite__glass-dome.jpg): Stained-glass oval dome over the stair hall (CC0, Procrastineur49)
- [`cercle-cite__gallery.jpg`](images/cercle-cite__gallery.jpg): Vaulted gallery / foyer with marble floor (CC0, Procrastineur49)
- [`cercle-cite__stair-landing.jpg`](images/cercle-cite__stair-landing.jpg): Upper landing with wrought-iron balustrade (CC0, Procrastineur49)

Plans / 3D: none found. Event-room capacities on cerclecite.lu (link only).

<a id="mnha"></a>
### Nationalmusée um Fëschmaart (MNAHA, National Museum of Archaeology, History and Art)

| | |
|---|---|
| Architects | New museum building by Christian Bauer & Associés (opened 2002), behind and below the historic Fish Market houses; later Wiltheim wing (2017) links the old houses. |
| Dates | Museum on this site since 1939 in old patrician houses; new wing 2002; Wiltheim wing 2017; reception renovated 2025. |
| Layout | A white natural-stone block on the Fish Market with a glazed hall; **three underground levels (about 700 m² each) dug into the rock** for archaeology; upper floors for fine arts and decorative arts (an Edward Steichen space planned on the 5th floor). |
| Main spaces | **Prehistory level** in the rock (rock walls left visible, reconstructions); **Gallo-Roman level** with the **Vichten mosaic** (3rd c., the nine Muses) in its own room; medieval and coin rooms; painting galleries (dark walls, spot lighting); period rooms in the old houses. |
| Materials, colours | White limestone, bare rock, dark grey gallery walls, glass. |
| Access | Tue–Sun, free for the permanent collection. |
| Official site | https://www.mnaha.lu/ |
| Wikipedia | [en: National Museum of Archaeology, History and Art](https://en.wikipedia.org/wiki/National_Museum_of_Archaeology,_History_and_Art) |

Images:
- [`mnha__prehistory-rock-level.jpg`](images/mnha__prehistory-rock-level.jpg): Underground prehistory level cut into the rock (CC BY-SA 4.0, FrDr)
- [`mnha__vichten-mosaic-room.jpg`](images/mnha__vichten-mosaic-room.jpg): Room of the Roman Vichten mosaic (CC BY-SA 4.0, FrDr)
- [`mnha__gallery.jpg`](images/mnha__gallery.jpg): Dark exhibition gallery with spot-lit artworks (CC0, Yourusernamewillbepublic2)

Plans: MNAHA brochure with map (2025, PDF, link only; shows the sites, may include the floor guide): https://mnaha.lu/assets/files/250403_MNAHA_Brochure-Map_Final_Single.pdf

3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/museum/national-museum-of-history-and-art-luxembourg ; MNAHA object scans on Sketchfab (see top).

<a id="city-museum"></a>
### Lëtzebuerg City Museum (Luxembourg City History Museum)

| | |
|---|---|
| Architects | Conny Lentz (Luxembourg) with Repérages (Paris). |
| Dates | Opened 22 June 1996; renamed from Musée d'histoire de la Ville de Luxembourg in May 2017. |
| Layout | Four restored town houses (17th–19th c., medieval traces) on Rue du Saint-Esprit joined by a modern glass façade and atrium; the rock beneath was excavated for **four extra levels**, giving **eight levels** in all. A **glass panoramic lift** (up to 60–65 people) runs through all of them: rock foundations at the bottom, views over the Grund and the Rham plateau at the top. |
| Main spaces | Rock-cut lower levels (archaeology, reconstructions), the permanent exhibition on the city's history through the floors, temporary-exhibition floors, the **city model / UNESCO visitor-centre room**, period rooms in the old houses. |
| Access | Tue–Sun; ticketed. |
| Official site | https://citymuseum.lu/ |
| Wikipedia | [en: Luxembourg City History Museum](https://en.wikipedia.org/wiki/Luxembourg_City_History_Museum) |

Images:
- [`city-museum__model-room.jpg`](images/city-museum__model-room.jpg): White room with the city model (UNESCO visitor centre) (CC BY-SA 4.0, FrDr)
- [`city-museum__rock-level-reconstruction.jpg`](images/city-museum__rock-level-reconstruction.jpg): Reconstruction in the rock-cut lower level (CC0, Van Der Meulen Christofle)

Plans: none public found. 3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/museum/letzebuerg-city-museum . The museum's own models of city buildings are described on citymuseum.lu (e.g. the Grand Théâtre model, https://citymuseum.lu/en/?p=3487).

<a id="saint-michel"></a>
### Saint-Michel Church (Église Saint-Michel)

| | |
|---|---|
| Dates | Oldest religious site in the city: castle chapel of 987. Destroyed and rebuilt several times; present church mostly rebuilt in **1688** after the French siege, keeping older Romanesque/Gothic parts; baroque portal of the same period. |
| Style | Mix of Gothic (rib vaults, pointed windows) and Baroque (portal, altars). |
| Layout | Small hall church with nave and side aisle on round columns, rib-vaulted; west gallery with the organ; polygonal choir. |
| Main features | Large **baroque high altar** (17th c.) with paintings and statues; side altar of the Madonna; organ gallery on columns; stained glass; St Michael statue. |
| Materials, colours | White walls and vaults, grey stone ribs and columns, dark gilded altars, coloured glass. |
| Access | Open daily, free. |
| Wikipedia | [en: St. Michael's Church, Luxembourg](https://en.wikipedia.org/wiki/St._Michael%27s_Church,_Luxembourg) |

Images:
- [`saint-michel__nave.jpg`](images/saint-michel__nave.jpg): Nave looking to the high altar: Gothic vault, baroque altar (CC BY-SA 3.0, Michael Kramer)
- [`saint-michel__choir.jpg`](images/saint-michel__choir.jpg): Choir and baroque high altar with stained glass (CC BY-SA 4.0, Diego Delso)
- [`saint-michel__organ-gallery.jpg`](images/saint-michel__organ-gallery.jpg): West organ gallery on columns (CC BY-SA 3.0, Chatsam)

Plans / 3D: none found. More photos: https://commons.wikimedia.org/wiki/Category:Interior_of_%C3%89glise_Saint-Michel_(Luxembourg_City)

<a id="casino-luxembourg"></a>
### Casino Luxembourg – Forum d'art contemporain

| | |
|---|---|
| Architects | Pierre Kemp and Pierre Funck (per the Casino's own history PDF; Wikipedia says Pierre and Paul Funck). 1959 glass pavilion ("Aquarium") by René Mailliet. Adapted for art in 1995 with Urs Raussmüller. |
| Dates | Built 1880–82 as the Casino Bourgeois (social club with ballroom and gaming); Franz Liszt gave his last recital here in July 1886; converted for European Capital of Culture 1995; contemporary art centre since 1996. |
| Style | Neo-Renaissance sandstone palace on Rue Notre-Dame/Boulevard Roosevelt; glass Aquarium (café/library) on the south. |
| Main spaces | White-cube exhibition rooms on the ground and first floor inside the historic shell (ornate ceilings partly kept), the former ballroom, the Aquarium, a white stair/"Artgalerio" circuit, a black-box room in the basement. |
| Access | Wed–Mon, ticketed (free on some days). |
| Official site | https://www.casino-luxembourg.lu/ ; history PDF https://casino-luxembourg.lu/sites/default/files/2021-11/The%20history.pdf |
| Wikipedia | [en: Casino Luxembourg](https://en.wikipedia.org/wiki/Casino_Luxembourg) |

Images:
- [`casino-luxembourg__staircase.jpg`](images/casino-luxembourg__staircase.jpg): White modern staircase inside the art centre (CC BY-SA 4.0, RG72)

Plans / 3D: none found. The history PDF above has historic views (link only).

<a id="spuerkeess"></a>
### Spuerkeess (BCEE) headquarters, Place de Metz

| | |
|---|---|
| Architect | Jean-Pierre Koenig (1870–1919), state architect. |
| Dates | Built 1910–13, inaugurated 15 Nov 1913; later extensions behind. |
| Style | Neo-Renaissance in a French manner with Art Nouveau touches; the tall **clock tower** with green copper cap is a city landmark. |
| Main spaces | Monumental entrance hall and historic banking hall (not documented on Commons); **Musée de la Banque** (bank museum) inside the building: vaults, old teller counter, safes, calculating machines, history of savings in Luxembourg. |
| Access | Bank museum free, Mon–Fri during office hours (check on spuerkeess.lu). |
| Official site | https://www.spuerkeess.lu/ |
| Wikipedia | [en: Spuerkeess Building](https://en.wikipedia.org/wiki/Spuerkeess_Building) |

Images:
- [`spuerkeess__bank-museum-vault.jpg`](images/spuerkeess__bank-museum-vault.jpg): Bank museum: old vault/strongroom display (CC BY-SA 3.0, LoKiLeCh)
- [`spuerkeess__bank-museum-counter.jpg`](images/spuerkeess__bank-museum-counter.jpg): Bank museum: reconstructed teller counter (CC BY-SA 3.0, LoKiLeCh)

Plans / 3D: none found. Bank-museum photos: https://commons.wikimedia.org/wiki/Category:Mus%C3%A9e_de_la_Banque

## Grund, Pfaffenthal and the fortress

<a id="neumunster-abbey"></a>
### Neimënster Abbey (Abbaye de Neumünster)

| | |
|---|---|
| Dates | Benedictine abbey moved to the Grund after its predecessor on the Altmünster plateau was destroyed (1543); rebuilt 1688–1720 after a fire; after 1796 a military hospital, then **prison 1869–1985**; restored and opened as cultural centre (Centre culturel de rencontre) in 2004. |
| Layout | Four long wings around a large paved **courtyard (parvis)** by the Alzette, next to the church of Saint-Jean; cloister wing; gardens. |
| Main rooms | **Agora Marcel Jullian** (494 m² covered courtyard under a filigree glass roof, the main entrance hall); **Salle Robert Krieps** (theatre/concert hall, 283 seats, former prison workshop); **cloister** with the Lucien Wercollier sculpture collection; **chapel** (baroque altar, stained glass); seminar rooms Nic Klecker and Lou Koster; brasserie; exhibition spaces. |
| Materials, colours | Ochre-yellow render, grey slate roofs, sandstone dressings; inside white plaster, stone floors, steel and glass in the new parts. |
| Access | Open daily, free (courtyard, Agora, cloister, exhibitions). |
| Official site | https://www.neimenster.lu/ (room pages, e.g. https://www.neimenster.lu/en/rooms/agora-marcel-jullian/) |
| Wikipedia | [en: Neumünster Abbey](https://en.wikipedia.org/wiki/Neum%C3%BCnster_Abbey) |

Images:
- [`neumunster-abbey__chapel-altar.jpg`](images/neumunster-abbey__chapel-altar.jpg): Chapel with baroque altar and stained glass (CC BY 4.0, Zinneke)
- [`neumunster-abbey__courtyard-aerial.jpg`](images/neumunster-abbey__courtyard-aerial.jpg): Raised view of the abbey courtyard and wings (layout reference) (CC BY-SA 2.0 de, Martin Röll)

Plans: the room pages on neimenster.lu give room sizes and capacities (link only); no free plan found. 3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/museum/neimenster . Commons has almost no interiors (one chapel photo); most files are exteriors.

<a id="saint-jean-grund"></a>
### Saint-Jean du Grund (Church of St John the Baptist)

| | |
|---|---|
| Dates | Former abbey church of Neumünster, consecrated **1705**; parish church of the Grund. |
| Style | Baroque interior in a late-Gothic-shaped hall (pointed windows, rib vaults). |
| Main features | Single nave with white vaults; large **baroque high altar** and side altars in black, gold and marble; **Black Madonna** (14th c.); **organ gallery** over the entrance with a historic organ; stained glass. |
| Access | Open daily, free. |
| Wikipedia | [en: St. John's Church, Luxembourg](https://en.wikipedia.org/wiki/St._John%27s_Church,_Luxembourg) |

Images:
- [`saint-jean-grund__nave.jpg`](images/saint-jean-grund__nave.jpg): Nave with baroque high altar and white vaults (CC BY-SA 4.0, Diego Delso)
- [`saint-jean-grund__organ-gallery.jpg`](images/saint-jean-grund__organ-gallery.jpg): Organ gallery (Stumm-type organ case) above the entrance (CC BY-SA 4.0, Diego Delso)
- [`saint-jean-grund__stained-glass.jpg`](images/saint-jean-grund__stained-glass.jpg): Stained-glass window (CC BY-SA 3.0 lu, Jwh)

Plans / 3D: none found. Commons category (mostly exteriors): https://commons.wikimedia.org/wiki/Category:%C3%89glise_Saint-Jean_(Neum%C3%BCnster)

<a id="natur-musee"></a>
### Natur Musée (National Museum of Natural History)

| | |
|---|---|
| Building | The former **Hospice Saint-Jean** in the Grund (17th–18th c. hospice buildings by the Alzette, next to Neimënster); baroque portal with the arms of Luxembourg and statues in niches. |
| Dates | Museum in this building since 1996 (permanent exhibition renewed since). |
| Layout | Long two-storey wings with dormered slate roofs around courtyards; exhibition halls on two floors, education rooms, café. |
| Access | Tue–Sun; ticketed. |
| Official site | https://www.mnhn.lu/ |
| Wikipedia | [en: National Museum of Natural History, Luxembourg](https://en.wikipedia.org/wiki/National_Museum_of_Natural_History,_Luxembourg) |

Images:
- [`natur-musee__workshop-room.jpg`](images/natur-musee__workshop-room.jpg): Interior room (workshop/education space) (CC BY-SA 4.0, RG72)

Plans: none found. 3D: the museum publishes many specimen scans on Sketchfab (https://sketchfab.com/mnhnl, mostly CC BY), not of the building. **Gap**: no photos of the exhibition halls on Commons.

<a id="bock-casemates"></a>
### Bock casemates (brief; see task 3)

| | |
|---|---|
| Dates | Galleries cut into the Bock rock from **1644** (Spanish), greatly extended under Vauban (after 1684) and the Austrians (1730s–1740s); at their peak 23 km of tunnels, about 17 km survive. Partly demolished after 1867; opened to the public in 1933. |
| Spaces | Rock-cut galleries on several levels with **cannon embrasures** opening onto the Alzette valley; stairs and shafts; the **Archaeological crypt** at the entrance with the foundations of Count Siegfried's castle (963). |
| Materials, colours | Raw yellow-grey Luxembourg sandstone, damp and dark, with modern lighting and steel walkways. |
| Access | Seasonal (roughly spring to autumn), ticketed. |
| Wikipedia | [en: Bock (Luxembourg)](https://en.wikipedia.org/wiki/Bock_(Luxembourg)) |

Images:
- [`bock-casemates__gallery.jpg`](images/bock-casemates__gallery.jpg): Rock-cut gallery inside the casemates (CC BY-SA 4.0, FrDr)
- [`bock-casemates__cannon-embrasure.jpg`](images/bock-casemates__cannon-embrasure.jpg): Embrasure with cannon looking out over the Alzette valley (CC BY-SA 4.0, FrDr)
- [`bock-casemates__archaeological-crypt.jpg`](images/bock-casemates__archaeological-crypt.jpg): Archaeological crypt: castle foundations under the Bock (CC BY-SA 4.0, FrDr)

Plans: task 3 covers casemate maps. 3D / virtual tour: tourist-office 360° tours of the Bock casemates (https://luxembourg-city.com/en/place/fortification/bock-casemates-lp) and the Archaeological crypt (https://luxembourg-city.com/en/place/fortification/archeological-crypt).

## Gare quarter

<a id="gare-centrale"></a>
### Gare Centrale (Luxembourg railway station)

| | |
|---|---|
| Architects | Alexander Rüdell, Karl Jüsgen and Scheuffel (German imperial railway architects). Hall ceiling redesigned in 1994 by Luxembourg artist **Armand Strainchamps**. 2010s modernisation with an ETFE-glazed passage, new passenger hall and underpasses. |
| Dates | Present building 1907–13; extended and modernised 2008–2012 and in the 2020s (new platforms and tracks 2021–25). |
| Style | Neo-Baroque (sometimes called "Mosel Baroque") with a tall clock tower. |
| Main spaces | **Main hall**: tall barrel-like space, cream walls, arched windows, departure boards; **painted ceiling** (sky with a large sun and black linework); the large semicircular **stained-glass window** with the **silhouette of the old city** (towers and spires in warm yellows, reds and blues); the **glass-roofed passage** to the platforms; shops and ticket office. |
| Access | Open all day, free. |
| Official site | https://www.cfl.lu/ |
| Wikipedia | [en: Luxembourg railway station](https://en.wikipedia.org/wiki/Luxembourg_railway_station) |

Images:
- [`gare-centrale__main-hall.jpg`](images/gare-centrale__main-hall.jpg): Main hall: painted ceiling, arched windows, departure boards (CC BY-SA 3.0, Basile Alexiou)
- [`gare-centrale__painted-ceiling.jpg`](images/gare-centrale__painted-ceiling.jpg): Painted ceiling with the sun motif (CC BY-SA 3.0, Basile Alexiou)
- [`gare-centrale__stained-glass-window.jpg`](images/gare-centrale__stained-glass-window.jpg): Stained-glass window with the silhouette of the city (CC BY-SA 3.0, Zoelux)
- [`gare-centrale__glass-passage.jpg`](images/gare-centrale__glass-passage.jpg): Modern glass-roofed passage (CC BY-SA 4.0, EEJCC)

Plans: government press file on the 2012 works with layout of the hall, passage and new underpass (PDF, link only): https://gouvernement.lu/dam-assets/fr/actualites/articles/2012/09-septembre/21-wiseler-gare/dossier.pdf . Platform notices with small station plans on cfl.lu (link only). 3D: none found.

<a id="villa-vauban"></a>
### Villa Vauban – Musée d'Art de la Ville de Luxembourg

| | |
|---|---|
| Dates | Villa built 1873 on the foundations of a Vauban-era fortification, in a park laid out by Édouard André; city art museum since 1959; restored and extended 2005–10 (reopened 2010) by architects **Diane Heirend & Philippe Schmit**. |
| Style | 19th-century villa (neoclassical) + a contemporary wing with exposed-aggregate concrete walls, timber floors and frosted glass. |
| Main spaces | Villa salons with stucco ceiling roses, parquet, used as painting galleries (Dutch and Flemish 17th c. and 19th-c. French paintings); original wooden staircase with cast-iron newel; new wing with top-lit galleries, timber stair and glazed corridor to the park. |
| Access | Wed–Mon, ticketed (free under 21). |
| Official site | https://villavauban.lu/ |
| Wikipedia | [en: Villa Vauban](https://en.wikipedia.org/wiki/Villa_Vauban) |

Images:
- [`villa-vauban__salon.jpg`](images/villa-vauban__salon.jpg): Villa salon with stucco ceiling rose and parquet, used as gallery (CC BY-SA 4.0, GilPe)
- [`villa-vauban__historic-staircase.jpg`](images/villa-vauban__historic-staircase.jpg): 19th-century wooden staircase with cast-iron newel (CC BY-SA 4.0, GilPe)
- [`villa-vauban__new-wing-stair.jpg`](images/villa-vauban__new-wing-stair.jpg): Stair in the 2010 extension: timber, exposed aggregate walls (CC BY-SA 4.0, GilPe)
- [`villa-vauban__new-wing-corridor.jpg`](images/villa-vauban__new-wing-corridor.jpg): Glazed corridor of the 2010 extension (CC BY-SA 4.0, GilPe)

Plans / 3D: none found.

<a id="grand-theatre"></a>
### Grand Théâtre de la Ville de Luxembourg

| | |
|---|---|
| Architect | Alain Bourbonnais (Paris), winner of the 1958 international competition. |
| Dates | Built 1959–64, opened 15 April 1964; renovated 2001–03 (stage machinery, acoustics, lighting). |
| Style | 1960s modernism: long glazed foyer front, façade panels with irregular hexagonal openings, mosaic and stone cladding. |
| Main spaces | **Grande salle** (943 seats, proscenium stage, opera and dance); **Studio** (adaptable black box, about 100–400 seats); long **foyer** with large hanging chandeliers and a wall pierced by irregular little windows. |
| Access | Performances; the foyer during events. |
| Official site | https://www.theatres.lu/ |
| Wikipedia | [en: Grand Théâtre de Luxembourg](https://en.wikipedia.org/wiki/Grand_Th%C3%A9%C3%A2tre_de_Luxembourg) |

Images (foyer only; no free photo of the auditorium):
- [`grand-theatre__foyer.jpg`](images/grand-theatre__foyer.jpg): Main foyer: long glazed hall with chandeliers (CC BY 3.0, Photo: Andreas Praefcke)
- [`grand-theatre__foyer-wall.jpg`](images/grand-theatre__foyer-wall.jpg): Foyer wall with irregular inset windows and chandeliers (CC BY 3.0, Photo: Andreas Praefcke)
- [`grand-theatre__foyer-chandeliers.jpg`](images/grand-theatre__foyer-chandeliers.jpg): Foyer chandeliers and glazing (CC BY 3.0, Photo: Andreas Praefcke)

Plans: seating plan of the Grande salle via the ticketing on theatres.lu (link only). 3D: the City Museum holds a model of the theatre (https://citymuseum.lu/en/?p=3487). Copyright on the architecture (Bourbonnais d. 1988) limits Commons.

## Kirchberg

<a id="philharmonie"></a>
### Philharmonie Luxembourg (Salle de concerts Grande-Duchesse Joséphine-Charlotte)

| | |
|---|---|
| Architect | Christian de Portzamparc. |
| Dates | Built 2002–05, opened June 2005. |
| Form | An eye-shaped (lens) plan wrapped by a screen of **823 white steel columns**; the foyer sits between the columns and the inner hall; two smaller halls are expressed as white sculptural volumes at the ends. |
| Main rooms | **Grand Auditorium** (about 1,500 seats, max 1,471 in rental terms): shoebox with the audience in stacked "towers" of boxes around the stage, white and light timber, a high organ (Schuke, 2005). **Salle de Musique de Chambre** (about 300 seats): curved red walls, a white suspended canopy with star-like point lights. **Espace Découverte** (about 120 places, for electronic/experimental music and children). Foyer with long ramps and stairs behind the colonnade. |
| Materials, colours | White steel and glass outside; inside white, light wood, red (chamber hall), grey stone floors. |
| Access | Concerts; guided architecture tours. |
| Official site | https://www.philharmonie.lu/ ; architecture page https://old.philharmonie.lu/en/service/architecture |
| Wikipedia | [en: Philharmonie Luxembourg](https://en.wikipedia.org/wiki/Philharmonie_Luxembourg) |

Images:
- [`philharmonie__grand-auditorium.jpg`](images/philharmonie__grand-auditorium.jpg): Grand Auditorium: shoebox hall with stacked box 'towers' around the stage (CC BY-SA 4.0, Clewe2807)
- [`philharmonie__chamber-music-hall.jpg`](images/philharmonie__chamber-music-hall.jpg): Chamber music hall: curved red walls and suspended canopy with point lights (CC BY-SA 4.0, Clewe2807)
- [`philharmonie__organ.jpg`](images/philharmonie__organ.jpg): Grand Auditorium organ and stage from the side (CC BY-SA 4.0, Zinneke)
- [`philharmonie__foyer.jpg`](images/philharmonie__foyer.jpg): Foyer between the outer colonnade and the inner hall (CC BY-SA 4.0, EEJCC)

Plans (all link only):
- Ground-floor plan and transverse section (1:666) in the Steeldoc PDF: https://beeldbank-nl.bouwenmetstaal.nl/pdf_serve/?id=CH2101
- Seating maps of the Grand Auditorium and the Chamber Music Hall: https://www.philharmonie.lu/en/faq and https://www.philharmonie.lu/en/support-engage/rent-the-phil/grand-auditorium
- Architects' photos: https://divisare.com/projects/341282-atelier-christian-de-portzamparc-christian-richters-wade-zimmerman-the-philharmonie-luxembourg ; acoustics description: https://www.baunetzwissen.de/akustik/objekte/kultur/philharmonie-in-luxemburg-l-69072

3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/monument/philharmonie-luxembourg

<a id="mudam"></a>
### Mudam (Musée d'Art Moderne Grand-Duc Jean)

| | |
|---|---|
| Architect | I. M. Pei (Pei Cobb Freed & Partners). |
| Dates | Commissioned 1989, built 1999–2006 on the walls of Fort Thüngen, opened 1 July 2006. |
| Form | Arrow-shaped plan following the fort's bastion; massive walls of French **Magny Doré limestone** (honey-coloured) with glass-and-steel roofs. |
| Floors | Exhibition spaces on three levels (0, -1, +1), about 6,000 m² public area (+1 = collection, over 800 m²). |
| Main spaces | **Grand Hall**: tall central space under a glazed steel lantern/pyramid; **Pavilion**: glass-roofed hall (café) with limestone walls; galleries on both wings; the curving stone **spiral staircases**; auditorium; shop. |
| Access | Wed–Mon, ticketed. |
| Official site | https://www.mudam.com/ (building and park: https://www.mudam.com/building-park ; accessibility/levels: https://www.mudam.com/visit/accessibility) |
| Wikipedia | [en: MUDAM](https://en.wikipedia.org/wiki/MUDAM) |

Images:
- [`mudam__grand-hall.jpg`](images/mudam__grand-hall.jpg): Grand Hall under I. M. Pei's glass and steel roof (CC BY-SA 3.0, Cornischong at Luxembourgish Wikipedia)
- [`mudam__pavilion.jpg`](images/mudam__pavilion.jpg): Glass-roofed pavilion with limestone walls (CC BY-SA 3.0 lu, Marco Musmeci)
- [`mudam__staircase.jpg`](images/mudam__staircase.jpg): Spiral stone staircase with glass balustrade (CC BY-SA 4.0, Hartmut Schmidt, Heidelberg)
- [`mudam__roof-structure.jpg`](images/mudam__roof-structure.jpg): Steel and glass roof structure of the Grand Hall (CC BY-SA 3.0 lu, Marco Musmeci)

Plans: plans and sections in the ArchEyes article (link only): https://archeyes.com/the-mudam-by-i-m-pei-where-old-meets-new/ ; project sheets https://archello.com/project/musee-dart-moderne . 3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/museum/mudam-museum-of-modern-art-grand-duc-jean-a-luxembourg

<a id="drai-eechelen"></a>
### Fort Thüngen / Musée Dräi Eechelen

| | |
|---|---|
| Dates | Fort built **1732–33** by the Austrians in front of the Grünewald front; named "Three Acorns" after the acorn finials on its three towers; mostly razed after 1867; walls rediscovered and **reconstructed** in the 1990s–2000s (alongside Mudam); museum opened **July 2012** (part of the MNAHA). Park by Michel Desvigne (2009). |
| Layout | Redoubt with three round towers on a bastion; the museum occupies the restored fort (vaulted rooms in the towers and curtain wall) plus a **new underground building** (exhibition hall and auditorium with glass floor panels showing the foundations), linked to the original **counter-mine galleries** that run under the glacis. |
| Main spaces | Exhibition rooms on Luxembourg history 1443–1903 (cannons, models, maps); the long, narrow, lit **mine galleries**; auditorium; reconstructed casemates. |
| Materials, colours | Grey-yellow sandstone and limestone, bare rock galleries, modern dark interiors with glass. |
| Access | Tue–Sun, free. |
| Official site | https://m3e.public.lu/ |
| Wikipedia | [en: Musée Dräi Eechelen](https://en.wikipedia.org/wiki/Mus%C3%A9e_Dr%C3%A4i_Eechelen) |

Images:
- [`drai-eechelen__mine-gallery.jpg`](images/drai-eechelen__mine-gallery.jpg): Narrow counter-mine gallery under the fort (CC BY-SA 4.0, RG72)
- [`drai-eechelen__exhibition-room.jpg`](images/drai-eechelen__exhibition-room.jpg): Exhibition room with cannons (CC BY-SA 4.0, RG72)
- [`drai-eechelen__auditorium.jpg`](images/drai-eechelen__auditorium.jpg): Modern auditorium/exhibition space with glass floor panels (CC BY-SA 4.0, Hejnjahns)

Plans: historic fortress plans are in task 3/4; the museum's gallery page https://m3e.public.lu/en/galeries.html (link only). 3D: CDF 3D scans of the Fort Thüngen casemates and galleries (2018), see top; tourist-office 360° tour https://luxembourg-city.com/en/place/museum/musee-drai-eechelen-luxembourg

<a id="cjeu"></a>
### Court of Justice of the European Union (Palais de la Cour de Justice)

| | |
|---|---|
| Architects | Ancien Palais (1973): Jean-Paul Conzemius, François Jamagne and Michel Vanden Haute. Extensions (Anneau, two towers, Gallery; renovation of the Ancien Palais): **Dominique Perrault**, competition 1996, inaugurated Dec 2008; **third tower** (Perrault) completed 2019, the tallest building in Luxembourg. |
| Layout | The Ancien Palais (courtrooms of the Court of Justice) is wrapped by the **Anneau**, a ring raised on slender columns that holds the judges' chambers; the **Gallery**, a long glazed street, links the Palais, the three gold-clad towers (translation services) and the Erasmus, Thomas More and Themis annexes (General Court). |
| Main rooms | **Grand courtroom** in the Ancien Palais: a huge canopy of bronze-anodised aluminium **gold metal mesh** (40 trapezoidal panels) over dark timber benches, interpreting booths around the top; other courtrooms in warm wood; **entrance hall** with black steel columns and flags; the Gallery (library, links); Rodin statue at the main stair. |
| Materials, colours | Gold/bronze mesh and anodised metal, dark wood, black steel, glass; outside rusty Cor-ten on the Anneau and gold-tinted glass towers. |
| Access | Public hearings are open to the public; free guided group visits on request (curia.europa.eu); open days. |
| Official site | https://curia.europa.eu/ |
| Wikipedia | [en: Palais de la Cour de Justice](https://en.wikipedia.org/wiki/Palais_de_la_Cour_de_Justice) |

Images:
- [`cjeu__grand-courtroom.jpg`](images/cjeu__grand-courtroom.jpg): Grand courtroom under the gold metal-mesh ceiling (CC BY 2.0, Cédric Puisney from Brussels, Belgium)
- [`cjeu__main-courtroom.jpg`](images/cjeu__main-courtroom.jpg): Main courtroom, wooden benches and judges' bench (CC BY-SA 4.0, Isderion)
- [`cjeu__entrance-hall.jpg`](images/cjeu__entrance-hall.jpg): Entrance hall of the Palais (black steel columns, flags) (CC BY-SA 4.0, Isderion)
- [`cjeu__gallery.jpg`](images/cjeu__gallery.jpg): Gallery building corridor linking the complex (CC BY-SA 4.0, FrDr)
- [`cjeu__architectural-model.jpg`](images/cjeu__architectural-model.jpg): Architectural model of the whole Palais complex (useful for 3D massing) (CC BY 2.0, Cédric Puisney from Brussels, Belgium)

Plans (link only): Dominique Perrault Architecture project page with drawings: https://www.perraultarchitecture.com/en/projects/2463-court_of_justice_of_the_european_union.html ; description and drawings on ArchiWeb: https://www.archiweb.cz/en/b/soudni-dvur-evropske-unie ; courtroom ceiling details by the mesh maker GKD: https://www.gkdmetalfabrics.com/wp-content/uploads/pdf/european-court-of-justice-interior.pdf

3D / virtual tour: tourist-office 360° tour https://luxembourg-city.com/en/place/monument/european-court-of-justice-luxembourg . The photo of the architectural model (`cjeu__architectural-model.jpg`) shows the whole complex from above.

<a id="bnl-kirchberg"></a>
### National Library (Bibliothèque nationale du Luxembourg, BnL), Kirchberg

| | |
|---|---|
| Architects | Bolles+Wilson (Münster) with WW+ architektur + management. |
| Dates | Competition 2003, long delay, detailed design from 2013; opened to the public 1 Oct 2019 on Avenue John F. Kennedy. |
| Form | A long building with a patterned façade (coloured ceramic "book spine" panels and red render); the **main reading room** is a terraced landscape of desks and shelves under a **long-span timber roof** carried on white **tree-like columns**. |
| Main spaces | Foyer and café; main reading room (terraces like an amphitheatre for reading); **upper reading deck**; **special reading room** in red for rare and old documents; open-plan offices on three levels around a light-filled atrium; closed stacks. |
| Materials, colours | White steel, light timber ceiling baffles, dark floors, white shelving; red and multicoloured façade. |
| Access | Free, Mon–Sat; reader card for borrowing. |
| Official site | https://bnl.public.lu/ |
| Wikipedia | [en: National Library of Luxembourg](https://en.wikipedia.org/wiki/National_Library_of_Luxembourg) |

Images:
- [`bnl-kirchberg__reading-room.jpg`](images/bnl-kirchberg__reading-room.jpg): Main reading room seen from above: terraced bookshelves and desks (CC BY-SA 4.0, Clewe2807)
- [`bnl-kirchberg__reading-room-columns.jpg`](images/bnl-kirchberg__reading-room-columns.jpg): Reading room with the white tree-like roof columns (CC BY-SA 4.0, GilPe)
- [`bnl-kirchberg__top-floor.jpg`](images/bnl-kirchberg__top-floor.jpg): Upper reading deck looking across the hall (CC BY-SA 4.0, Atharva210)
- [`bnl-kirchberg__foyer.jpg`](images/bnl-kirchberg__foyer.jpg): Ground-floor foyer (CC BY-SA 4.0, GilPe)

Plans (link only): site plan, ground-floor plan and longitudinal section by Bolles+Wilson in the World-Architects article: https://world-architects.com/it/architecture-news/insight/worth-the-wait ; architects' project page with photos: https://bolles-wilson.com/project/bnl-bibliotheque-nationale-du-luxembourg/ ; ArchDaily (drawings): https://www.archdaily.com/958382/luxembourg-national-library-bolles-plus-wilson-plus-ww-plus-architektur-plus-management . 3D: none found.

## Gaps

- **Hôtel de Ville**: no free interior photo, no plan, no tour.
- **Grand Ducal Palace**: only three usable interior photos (two older room photos and one official-visit photo); photography is banned on tours; no plan.
- **Grand Théâtre auditorium, Casino Luxembourg exhibition rooms, Natur Musée halls, Neimënster interiors (Agora, Salle Krieps, cloister), City Museum glass lift, Spuerkeess banking hall**: not on Commons. Mostly a copyright (no freedom of panorama) or simply nobody-uploaded problem; institutions' own photos are the fallback (link only).
- **Plans**: no free modern plan of any building was found. The best published plans are for the Philharmonie (Steeldoc PDF), BnL (World-Architects), CJEU (Perrault) and Mudam (ArchEyes); everything else needs tracing from OSM/cadastre footprints (geoportail.lu) plus photos.
- **3D**: no free building models; only official 360° tours (not reusable) and MNAHA/CDF scans of fortress galleries.
- Some facts conflict between sources and are flagged in the text (Casino architects, Cercle Cité construction dates, Philharmonie seat count).
