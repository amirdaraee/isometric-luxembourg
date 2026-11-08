# 01 – Landmarks: pictures and key facts

Reference photos for 129 landmarks of Luxembourg City (see "Citywide additions" at the end for the 82 added in November 2026, with facts and sources). The first 47: the 36 FEATURED entries of `pipeline/build_places.py` plus 11 additions (fortress sites, Corniche, Place de la Constitution, Kirchberg towers, City History Museum). 143 images, 124 MB, all from Wikimedia Commons as ~1600 px wide thumbnails (smaller if the original is smaller).

How to use this folder:
- `images/<slug>__<what>.jpg`: `aerial`/`drone`/`raised-view`/`panorama` are the most useful for isometric massing and roof shapes; `detail-*` for ornament, materials and colour; `interior*` for 3D/interior views; `historic*` are period images or drawings.
- `sources.json`: one record per file with `source_page`, `author`, `licence` and `licence_url`. Every file is CC0, public domain, CC BY or CC BY-SA. **Attribution is required for all CC BY / CC BY-SA files, and CC BY-SA derivatives must be shared alike** if any of these photos (or close traces of them) end up in published material. Used only as drawing reference, they leave no trace in the art.
- Coordinates are WGS84 lat/lon, taken from the project's OSM extract (`data/raw/osm/places.json`) for FEATURED entries (the OSM name given is the exact name matched by `build_places.py`), and from OSM or Wikidata for the additions.
- The 19-photo series *Aerial views of European Union Capitals – Luxembourg* (European Commission, CC BY 4.0) is the best source of true aerial views; it covers the cathedral, Gëlle Fra, Pont Adolphe, Spuerkeess, Passerelle, Pétrusse valley, Red Bridge, Porte de l'Europe, Philharmonie, Court of Justice, Mudam and Fort Thüngen. Series files not used here (05, 10, 17 'Old Town Suburbs', 02, 03, 11) are worth a look: https://commons.wikimedia.org/w/index.php?search=%22Aerial+views+of+European+Union+Capitals+-+Luxembourg%22&ns6=1

**Freedom of panorama caveat.** Luxembourg has no freedom-of-panorama exception, so Commons removes or blurs photos of copyrighted buildings and artworks whose authors died less than 70 years ago. This is why recent architecture (d'Coque, Philharmonie, Mudam, Red Bridge, KAD, Court of Justice towers, the Pfaffenthal lift, the Gëlle Fra statue by Claus Cito, d. 1965) is thin or patchy on Commons, and some files that are there now may be deleted later. The licences recorded here are those stated on Commons at download time (November 2026).

## Gaps and weak spots

- **d'Coque**: no good free exterior. Only a street view where the roof edge shows and a tram-stop photo with the building blurred on Commons. Use OSM footprints, satellite imagery or the operator's own photos (link only) for the shell roof.
- **University of Luxembourg, Kirchberg campus**: a single (older) aerial; the campus has few free photos. Most of the university now sits at Belval, outside the map.
- **Kirchberg Shopping Center (Auchan)**: two images, both functional; no aerial.
- **Pétrusse casemates**: interiors only; the entrance on Place de la Constitution is in the Place de la Constitution / Gëlle Fra photos.
- **Wenceslas Wall**: one modern exterior plus an old photo of the Rham-plateau towers under restoration; the best views of the wall are the Grund/Stierchen raised views (`grund-stierchen__raised-view.jpg`, `bock-promontory__panorama.jpg`).
- **Grund lock (Écluse du Grund)**: no clearly identified photo of the lock itself; the weir and Stierchen bridge photos show the river section around it.
- **Saint-Esprit citadel**: free photos are few and of modest quality; the citadel walls also appear in the Grund panoramas.
- **Municipal Park, Parc Central, Spuerkeess, Villa Vauban**: no aerial views apart from the EU aerials listed above.
- **Interiors**: only a handful (cathedral is exterior-only here; interiors of the Philharmonie, Court of Justice, Saint-Jean, MNHA, casemates are included). Task 2 (`02-buildings-interiors/`) should go deeper.

## Index

- **Old town (Ville Haute)**: [Notre-Dame Cathedral](#cathedral), [Grand Ducal Palace](#grand-ducal-palace), [Chamber of Deputies](#chamber-of-deputies), [City Hall](#hotel-de-ville), [Place Guillaume II (Knuedler)](#place-guillaume-ii), [Place d'Armes](#place-darmes), [Cercle Cité (Cercle municipal)](#cercle-cite), [National Museum of History and Art](#mnha), [Luxembourg City History Museum](#city-museum), [St. Michael's Church](#saint-michel), [Casino Luxembourg – Forum of contemporary art](#casino-luxembourg), [Place de la Constitution](#place-de-la-constitution), [Gëlle Fra (Monument of Remembrance)](#gelle-fra), [Chemin de la Corniche](#chemin-de-la-corniche)
- **Fortress, casemates and the Grund**: [Bock promontory (Lucilinburhuc castle site)](#bock-promontory), [Bock Casemates](#bock-casemates), [Pétrusse Casemates](#petrusse-casemates), [Three Towers Gate](#three-towers), [Spanish Turrets](#spanish-turrets), [Wenceslas Wall](#wenzel-wall), [Grund lock and Stierchen bridge](#grund-stierchen), [Saint-Esprit Citadel](#saint-esprit-citadel), [Fort Obergrünewald](#fort-obergrunewald), [Fort Thüngen / Three Acorns Museum](#drai-eechelen), [Neumünster Abbey](#neumunster-abbey), [Church of St. John the Baptist, Grund](#saint-jean-grund), [National Museum of Natural History](#natur-musee)
- **Bridges, valleys and parks**: [Adolphe Bridge](#pont-adolphe), [Passerelle (Old Viaduct)](#passerelle), [Grand Duchess Charlotte Bridge (Red Bridge)](#red-bridge), [Clausen railway viaduct](#clausen-viaduct), [Pfaffenthal Panoramic Lift](#pfaffenthal-lift), [Pétrusse Valley](#petrusse-valley), [Municipal Park](#municipal-park), [Villa Vauban](#villa-vauban)
- **Gare quarter**: [Spuerkeess (BCEE) headquarters and clock tower](#spuerkeess-tower), [Luxembourg railway station](#gare-centrale)
- **Kirchberg**: [Pfaffenthal-Kirchberg station and funicular](#pfaffenthal-kirchberg-station), [Porte de l'Europe and Kirchberg towers](#kirchberg-towers), [Philharmonie Luxembourg](#philharmonie), [Mudam (Grand Duke Jean Museum of Modern Art)](#mudam), [Court of Justice of the European Union](#cjeu-towers), [European Parliament, Konrad Adenauer Building](#european-parliament-kad), [d'Coque](#coque), [Kirchberg Central Park (Arboretum)](#kirchberg-parc-central), [University of Luxembourg, Kirchberg campus](#university-kirchberg), [Auchan Kirchberg shopping centre](#kirchberg-shopping-center)

## Old town (Ville Haute)

<a id="cathedral"></a>
### Notre-Dame Cathedral

| | |
|---|---|
| Local name | Cathédrale Notre-Dame |
| OSM name | `Cathédrale Notre-Dame de Luxembourg` |
| Coordinates | 49.60981, 6.13156 |
| Category | landmark |
| About | Begun in 1613 as the Jesuit college church (architect Jean du Blocq): late Gothic in structure with Renaissance and Baroque ornament; it became the cathedral in 1870 and was greatly enlarged eastwards in 1935–38 by Hubert Schumacher. Pale yellow-grey sandstone walls and grey slate roofs; the skyline signature is two needle-thin dark spires at the east end plus a third, older west tower. The crypt holds the grand-ducal burial vault and the tomb of John the Blind. |
| Images | [`cathedral__aerial.jpg`](images/cathedral__aerial.jpg): Aerial view of the cathedral spires with the Gëlle Fra and Place de la Constitution<br>[`cathedral__drone.jpg`](images/cathedral__drone.jpg): Drone shot of the cathedral from above<br>[`cathedral__exterior.jpg`](images/cathedral__exterior.jpg): Exterior of the cathedral<br>[`cathedral__exterior-choir.jpg`](images/cathedral__exterior-choir.jpg): Exterior of the transept and choir |
| Wikipedia | [en: Notre-Dame Cathedral, Luxembourg](https://en.wikipedia.org/wiki/Notre-Dame_Cathedral,_Luxembourg) |

<a id="grand-ducal-palace"></a>
### Grand Ducal Palace

| | |
|---|---|
| Local name | Palais grand-ducal |
| OSM name | `Palais Grand Ducal` |
| Coordinates | 49.61099, 6.13291 |
| Category | landmark |
| About | Built from 1572 as the city hall, extended in the 18th century and again in the 1890s, it has been the Grand Duke's town residence since 1890. The Renaissance façade is honey-coloured sandstone covered in fine geometric carving in a Spanish-Moorish-influenced style, with oriel turrets topped by slender slate spires and a steep dark roof with dormers. Guards in a sentry box stand at the door on the Rue du Marché-aux-Herbes. |
| Images | [`grand-ducal-palace__facade.jpg`](images/grand-ducal-palace__facade.jpg): Main façade from the Rue du Marché-aux-Herbes<br>[`grand-ducal-palace__exterior-with-chamber.jpg`](images/grand-ducal-palace__exterior-with-chamber.jpg): Palace and the adjoining Chamber of Deputies<br>[`grand-ducal-palace__detail-windows-roof.jpg`](images/grand-ducal-palace__detail-windows-roof.jpg): Detail: windows, sgraffito and roof |
| Wikipedia | [en: Grand Ducal Palace, Luxembourg](https://en.wikipedia.org/wiki/Grand_Ducal_Palace,_Luxembourg) |

<a id="chamber-of-deputies"></a>
### Chamber of Deputies

| | |
|---|---|
| Local name | Chambre des Députés |
| OSM name | `Chambre des Députés` |
| Coordinates | 49.61069, 6.13316 |
| Category | landmark |
| About | Hôtel de la Chambre, the parliament building, built 1858–1860 directly adjoining the Grand Ducal Palace. Neo-Renaissance façade in light sandstone with arched windows and decorative carving, flags at the entrance; much smaller and plainer than the palace next to it. |
| Images | [`chamber-of-deputies__facade.jpg`](images/chamber-of-deputies__facade.jpg): Façade of the parliament building<br>[`chamber-of-deputies__exterior.jpg`](images/chamber-of-deputies__exterior.jpg): Exterior on the Rue du Marché-aux-Herbes<br>[`chamber-of-deputies__detail.jpg`](images/chamber-of-deputies__detail.jpg): Detail of the façade |
| Wikipedia | [en: Chamber of Deputies (Luxembourg)](https://en.wikipedia.org/wiki/Chamber_of_Deputies_(Luxembourg)) |

<a id="hotel-de-ville"></a>
### City Hall

| | |
|---|---|
| Local name | Hôtel de Ville |
| OSM name | `Hôtel de Ville` |
| Coordinates | 49.61020, 6.13049 |
| Category | landmark |
| About | City Hall on Place Guillaume II, built 1830–1838 in a sober neoclassical style on the site of the old Franciscan friary. Pale stone façade with a row of tall windows and a portico; two bronze lions guard the steps. |
| Images | [`hotel-de-ville__facade.jpg`](images/hotel-de-ville__facade.jpg): Neoclassical façade with its lions<br>[`hotel-de-ville__with-square.jpg`](images/hotel-de-ville__with-square.jpg): City Hall, the square and the cathedral<br>[`hotel-de-ville__corner.jpg`](images/hotel-de-ville__corner.jpg): Corner view of the City Hall block |
| Wikipedia | [en: Luxembourg City Hall](https://en.wikipedia.org/wiki/Luxembourg_City_Hall) |

<a id="place-guillaume-ii"></a>
### Place Guillaume II (Knuedler)

| | |
|---|---|
| Local name | Place Guillaume II / Knuedler |
| OSM name | `Guillaume II` |
| Coordinates | 49.61068, 6.13130 |
| Category | square |
| About | The Knuedler, the city's largest square, on the site of a former Franciscan friary (named after the friars' knotted belts). The equestrian statue of King-Grand Duke William II by Antonin Mercié stands in the middle, with the City Hall on one side. Used for markets and events; large paved open space framed by pastel town houses. |
| Images | [`place-guillaume-ii__city-hall-night.jpg`](images/place-guillaume-ii__city-hall-night.jpg): The square and City Hall at night<br>[`place-guillaume-ii__raised-view.jpg`](images/place-guillaume-ii__raised-view.jpg): Square seen from the City Hall<br>[`place-guillaume-ii__statue.jpg`](images/place-guillaume-ii__statue.jpg): The equestrian statue of William II |
| Wikipedia | [en: Place Guillaume II](https://en.wikipedia.org/wiki/Place_Guillaume_II) |

<a id="place-darmes"></a>
### Place d'Armes

| | |
|---|---|
| Local name | Place d'Armes / Plëss |
| OSM name | `Kiosque de la Place d'Armes` |
| Coordinates | 49.61126, 6.12911 |
| Category | square |
| About | The old town's main café square, laid out in the 17th century as a parade ground for the garrison (hence the name). Lined with plane trees, with a bandstand used for summer concerts, and the Cercle Cité on its east side. Pink and grey paving, café terraces, a Christmas market in winter. |
| Images | [`place-darmes__square.jpg`](images/place-darmes__square.jpg): The square with its trees and bandstand<br>[`place-darmes__square-market.jpg`](images/place-darmes__square-market.jpg): Flea market on the square<br>[`place-darmes__detail-bandstand.jpg`](images/place-darmes__detail-bandstand.jpg): The bandstand<br>[`place-darmes__square-2.jpg`](images/place-darmes__square-2.jpg): View over the square with the bandstand |
| Wikipedia | [en: Place d'Armes (Luxembourg)](https://en.wikipedia.org/wiki/Place_d'Armes_(Luxembourg)) |

<a id="cercle-cite"></a>
### Cercle Cité (Cercle municipal)

| | |
|---|---|
| Local name | Cercle Cité |
| OSM name | `Cercle municipal` |
| Coordinates | 49.61137, 6.13018 |
| Category | culture |
| About | Cercle municipal, built 1904–1909 for city receptions and events, now Cercle Cité with exhibition rooms. Ornate Beaux-Arts style façade in cream stone facing Place d'Armes, with a clock under a sculpted pediment and a long relief frieze of Countess Ermesinde granting the city its charter of freedoms in 1244. |
| Images | [`cercle-cite__facade.jpg`](images/cercle-cite__facade.jpg): Façade on Place d'Armes<br>[`cercle-cite__detail-top.jpg`](images/cercle-cite__detail-top.jpg): Detail: top of the façade with sculpture<br>[`cercle-cite__detail-clock.jpg`](images/cercle-cite__detail-clock.jpg): Detail: the clock |
| Wikipedia | [en: Cercle Municipal](https://en.wikipedia.org/wiki/Cercle_Municipal) |

<a id="mnha"></a>
### National Museum of History and Art

| | |
|---|---|
| Local name | Musée national d'histoire et d'art |
| OSM name | `Musée national d'histoire et d'art Luxembourg` |
| Coordinates | 49.61172, 6.13372 |
| Category | culture |
| About | National Museum of Archaeology, History and Art on the Fëschmaart, the old fish market at the heart of the medieval town. Its main building (2002) is a smooth white limestone cube that goes deep into the rock, connected to restored historic town houses. Collections run from prehistory and Gallo-Roman mosaics to modern art. |
| Images | [`mnha__interior-gallery.jpg`](images/mnha__interior-gallery.jpg): Interior: exhibition gallery<br>[`mnha__interior.jpg`](images/mnha__interior.jpg): Inside the museum<br>[`mnha__interior-2.jpg`](images/mnha__interior-2.jpg): Inside the museum<br>[`mnha__exterior.jpg`](images/mnha__exterior.jpg): Exterior on the Marché-aux-Poissons<br>[`mnha__entrance.jpg`](images/mnha__entrance.jpg): Entrance on the Fëschmaart |
| Wikipedia | [en: National Museum of Archaeology, History and Art](https://en.wikipedia.org/wiki/National_Museum_of_Archaeology,_History_and_Art) |

<a id="city-museum"></a>
### Luxembourg City History Museum

| | |
|---|---|
| Local name | Lëtzebuerg City Museum / Musée d'Histoire de la Ville |
| OSM name | (not in FEATURED) |
| Coordinates | 49.60997, 6.13363 |
| Category | culture |
| About | The Lëtzebuerg City Museum on the Rue du Saint-Esprit, opened 1996 in four restored town houses from the 17th to 19th centuries. Its large glass panoramic lift drops through the rock and has views over the Grund; inside, fortress models and the history of the city. |
| Images | [`city-museum__view.jpg`](images/city-museum__view.jpg): View over the old town roofs towards the Grund (filed under the museum on Commons)<br>[`city-museum__exterior-2.jpg`](images/city-museum__exterior-2.jpg): Museum exterior<br>[`city-museum__exhibit.jpg`](images/city-museum__exhibit.jpg): Exhibit inside the museum (reconstructed prehistoric shelter) |
| Wikipedia | [en: Luxembourg City History Museum](https://en.wikipedia.org/wiki/Luxembourg_City_History_Museum) |

<a id="saint-michel"></a>
### St. Michael's Church

| | |
|---|---|
| Local name | Église Saint-Michel |
| OSM name | `Église de Saint-Michel` |
| Coordinates | 49.61123, 6.13486 |
| Category | landmark |
| About | The oldest religious site in the city: a chapel of the counts' castle stood here from the late 10th century. The present church mixes Romanesque, Gothic and Baroque parts; it was rebuilt after the French siege, with a Baroque portal of the 1680s. Ochre walls, an onion-domed bell tower and a statue of Saint Michael with the dragon. |
| Images | [`saint-michel__exterior.jpg`](images/saint-michel__exterior.jpg): The church and its tower<br>[`saint-michel__portal.jpg`](images/saint-michel__portal.jpg): The 1687 portal<br>[`saint-michel__detail-statue.jpg`](images/saint-michel__detail-statue.jpg): Detail: Saint Michael and the dragon |
| Wikipedia | [en: Saint Michael's Church, Luxembourg](https://en.wikipedia.org/wiki/Saint_Michael's_Church,_Luxembourg) |

<a id="casino-luxembourg"></a>
### Casino Luxembourg – Forum of contemporary art

| | |
|---|---|
| Local name | Casino Luxembourg – Forum d'art contemporain |
| OSM name | `Casino Luxembourg - Forum d'art contemporain` |
| Coordinates | 49.60978, 6.12717 |
| Category | culture |
| About | Built 1880–1882 as the 'Casino bourgeois', a society club where Franz Liszt gave his last concert in 1886; since 1996 the Casino Luxembourg – Forum d'art contemporain. Cream stone neo-Renaissance façade on Boulevard Roosevelt with a modern glass ground-floor extension. |
| Images | [`casino-luxembourg__facade.jpg`](images/casino-luxembourg__facade.jpg): Façade on Boulevard Roosevelt<br>[`casino-luxembourg__exterior.jpg`](images/casino-luxembourg__exterior.jpg): Front view<br>[`casino-luxembourg__detail-plaque.jpg`](images/casino-luxembourg__detail-plaque.jpg): Detail: commemorative bronze plaque on the building |
| Wikipedia | [en: Casino Luxembourg](https://en.wikipedia.org/wiki/Casino_Luxembourg) |

<a id="place-de-la-constitution"></a>
### Place de la Constitution

| | |
|---|---|
| Local name | Place de la Constitution |
| OSM name | (not in FEATURED) |
| Coordinates | 49.60940, 6.12921 |
| Category | square |
| About | Square on the Beck bastion above the Pétrusse valley, home to the Gëlle Fra and the entrance to the Pétrusse casemates. Views of the Pont Adolphe and the Spuerkeess tower; site of the Christmas market and funfair wheel in winter. |
| Images | [`place-de-la-constitution__aerial.jpg`](images/place-de-la-constitution__aerial.jpg): Aerial view of the square, Gëlle Fra and the cathedral<br>[`place-de-la-constitution__raised-view.jpg`](images/place-de-la-constitution__raised-view.jpg): The square seen from the cathedral tower<br>[`place-de-la-constitution__square-funfair.jpg`](images/place-de-la-constitution__square-funfair.jpg): The square with the Christmas funfair wheel |
| Wikipedia | [de: Place de la Constitution](https://de.wikipedia.org/wiki/Place_de_la_Constitution) |

<a id="gelle-fra"></a>
### Gëlle Fra (Monument of Remembrance)

| | |
|---|---|
| Local name | Monument du Souvenir / Gëlle Fra |
| OSM name | `Monument du souvenir` |
| Coordinates | 49.60930, 6.12937 |
| Category | landmark |
| About | The Monument of Remembrance by sculptor Claus Cito, unveiled in 1923 for Luxembourgers who served in the First World War. A gilded bronze woman holding up a laurel wreath stands on a tall granite obelisk (about 21 m), with two bronze soldiers at the base. Pulled down by the Nazi occupiers in 1940, it was pieced back together and re-erected in 1985. The golden figure is a key colour accent on the Place de la Constitution. |
| Images | [`gelle-fra__aerial.jpg`](images/gelle-fra__aerial.jpg): Aerial view of the monument on Place de la Constitution with the cathedral<br>[`gelle-fra__exterior.jpg`](images/gelle-fra__exterior.jpg): South face of the monument with the obelisk<br>[`gelle-fra__detail-statue.jpg`](images/gelle-fra__detail-statue.jpg): Detail: the gilded figure on the obelisk |
| Wikipedia | [en: Gëlle Fra](https://en.wikipedia.org/wiki/G%C3%ABlle_Fra) |

<a id="chemin-de-la-corniche"></a>
### Chemin de la Corniche

| | |
|---|---|
| Local name | Chemin de la Corniche / Corniche |
| OSM name | (not in FEATURED) |
| Coordinates | 49.60981, 6.13413 |
| Category | viewpoint |
| About | A promenade along the 17th-century rampart walls above the Grund, often called 'the most beautiful balcony in Europe'. Cobbled walkway, parapet walls and trees, with views over Neumünster Abbey, the Alzette and the Rham plateau. |
| Images | [`chemin-de-la-corniche__exterior.jpg`](images/chemin-de-la-corniche__exterior.jpg): The Corniche rampart<br>[`chemin-de-la-corniche__promenade.jpg`](images/chemin-de-la-corniche__promenade.jpg): The promenade<br>[`chemin-de-la-corniche__view-from.jpg`](images/chemin-de-la-corniche__view-from.jpg): View of the Grund from the Corniche |
| Wikipedia | [de: Corniche (Luxemburg)](https://de.wikipedia.org/wiki/Corniche_(Luxemburg)) |

## Fortress, casemates and the Grund

<a id="bock-promontory"></a>
### Bock promontory (Lucilinburhuc castle site)

| | |
|---|---|
| Local name | Rocher du Bock / Bockfiels |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61141, 6.13620 |
| Category | history |
| About | The rocky spur over the Alzette where Count Siegfried acquired the castle site of Lucilinburhuc in 963, the founding date of Luxembourg. The castle was demolished with the fortress after 1867; what remains are cliffs, casemate openings and the Schlassbréck (castle bridge). Yellow-brown sandstone cliffs with walls on top. |
| Images | [`bock-promontory__exterior.jpg`](images/bock-promontory__exterior.jpg): The Bock promontory<br>[`bock-promontory__panorama.jpg`](images/bock-promontory__panorama.jpg): Panorama: Grund, Ville Haute, Bock and Kirchberg<br>[`bock-promontory__castle-bridge.jpg`](images/bock-promontory__castle-bridge.jpg): The Bock and the castle bridge<br>[`bock-promontory__historic-drawing.jpg`](images/bock-promontory__historic-drawing.jpg): Historic drawing of the Bock by Michel Engels |
| Wikipedia | [en: Lucilinburhuc](https://en.wikipedia.org/wiki/Lucilinburhuc) |

<a id="bock-casemates"></a>
### Bock Casemates

| | |
|---|---|
| Local name | Casemates du Bock |
| OSM name | `Casemates du Bock` |
| Coordinates | 49.61166, 6.13669 |
| Category | history |
| About | Galleries and gun chambers cut into the Bock rock, begun under Spanish rule in the 1640s and extended by Vauban and the Austrians in the 18th century; the whole city once had about 23 km of casemates, of which some 17 km survive. Raw yellow-brown sandstone tunnels, cannon embrasures opening onto the Alzette valley, and a stone bridge (the Schlassbréck) leading to them. Part of the UNESCO World Heritage site since 1994. |
| Images | [`bock-casemates__interior-lit.jpg`](images/bock-casemates__interior-lit.jpg): Interior: lit gallery in the Bock casemates<br>[`bock-casemates__interior-gallery.jpg`](images/bock-casemates__interior-gallery.jpg): Interior: a casemate gallery<br>[`bock-casemates__detail-bridge.jpg`](images/bock-casemates__detail-bridge.jpg): The bridge leading to the Bock casemates<br>[`bock-casemates__exterior.jpg`](images/bock-casemates__exterior.jpg): View from the Grund up to the casemates in the Bock rock |
| Wikipedia | [en: Bock (Luxembourg)](https://en.wikipedia.org/wiki/Bock_(Luxembourg)) |

<a id="petrusse-casemates"></a>
### Pétrusse Casemates

| | |
|---|---|
| Local name | Casemates de la Pétrusse |
| OSM name | `Pétrusse Casemates` |
| Coordinates | 49.60943, 6.12993 |
| Category | history |
| About | Casemates dug in the 1640s under the Beck bastion, below today's Place de la Constitution, with staircases descending deep into the rock towards the Pétrusse valley. Closed for years for safety work, they reopened in the 2020s with new lighting. Rough sandstone vaults, steep narrow stairs and gun ports looking over the valley. |
| Images | [`petrusse-casemates__interior.jpg`](images/petrusse-casemates__interior.jpg): Interior of the casemates after reopening<br>[`petrusse-casemates__interior-gallery.jpg`](images/petrusse-casemates__interior-gallery.jpg): Interior gallery<br>[`petrusse-casemates__detail.jpg`](images/petrusse-casemates__detail.jpg): Detail inside the casemates |
| Wikipedia | [lb: Péitruss-Kasematten](https://lb.wikipedia.org/wiki/P%C3%A9itruss-Kasematten) |

<a id="three-towers"></a>
### Three Towers Gate

| | |
|---|---|
| Local name | Porte des Trois Tours / Dräi Tierm |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61253, 6.13336 |
| Category | history |
| About | The 'Three Towers' gate (Dräi Tierm, also Porte du Pfaffenthal) on the medieval walls: the innermost tower goes back to the city's first wall around 1050, the other two were added in the late Middle Ages. Three round sandstone towers with conical slate roofs, side by side over a gateway. |
| Images | [`three-towers__exterior.jpg`](images/three-towers__exterior.jpg): The Three Towers gate<br>[`three-towers__raised-view.jpg`](images/three-towers__raised-view.jpg): The gate seen from the Rue du Nord, above<br>[`three-towers__historic.jpg`](images/three-towers__historic.jpg): Historic photograph by Charles Bernhoeft |
| Wikipedia | [de: Drei Türme (Luxemburg)](https://de.wikipedia.org/wiki/Drei_T%C3%BCrme_(Luxemburg)) |

<a id="spanish-turrets"></a>
### Spanish Turrets

| | |
|---|---|
| Local name | Tourelles espagnoles / Spuenesch Tiermchen |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61566, 6.13692 |
| Category | history |
| About | Small stone sentry turrets (bartizans) with pointed roofs on the fortress walls, especially along the Montée de Pfaffenthal. Popularly called 'Spanish', though most date from later French and Austrian rebuilding. Pale stone with slate or metal caps, perched over steep drops. |
| Images | [`spanish-turrets__exterior.jpg`](images/spanish-turrets__exterior.jpg): A Spanish turret on the walls<br>[`spanish-turrets__bartizan.jpg`](images/spanish-turrets__bartizan.jpg): Bartizan over the Montée de Pfaffenthal<br>[`spanish-turrets__detail.jpg`](images/spanish-turrets__detail.jpg): Detail of a turret |
| Wikipedia | [de: Spanische Türmchen](https://de.wikipedia.org/wiki/Spanische_T%C3%BCrmchen) |

<a id="wenzel-wall"></a>
### Wenceslas Wall

| | |
|---|---|
| Local name | Mur de Wenceslas / Wenzelsmauer |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61155, 6.13729 |
| Category | history |
| About | Part of the city's late-14th-century ring wall built under Duke Wenceslas II, crossing the Alzette valley from the Bock to the Rham plateau. Stretches of rubble-stone wall with round towers, gateways and the Stierchen bridge survive; the 'Wenzel circular walk' follows it. |
| Images | [`wenzel-wall__exterior.jpg`](images/wenzel-wall__exterior.jpg): The Wenzel wall<br>[`wenzel-wall__rham-wall.jpg`](images/wenzel-wall__rham-wall.jpg): The medieval wall on the Rham plateau |
| Wikipedia | [en: Fortress of Luxembourg](https://en.wikipedia.org/wiki/Fortress_of_Luxembourg) |

<a id="grund-stierchen"></a>
### Grund lock and Stierchen bridge

| | |
|---|---|
| Local name | Écluse du Grund / Pont du Stierchen |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61130, 6.13743 |
| Category | bridge |
| About | The Stierchen is a small medieval footbridge over the Alzette that forms part of the Wenceslas Wall, with a round tower at one end. Just upstream, the Grund lock (Écluse du Grund) was a fortress water barrier that could flood the valley. Stone arches, weir, rubble walls and the Bock cliffs behind. |
| Images | [`grund-stierchen__weir-and-bridge.jpg`](images/grund-stierchen__weir-and-bridge.jpg): The Alzette weir with the Stierchen bridge and the Bock behind<br>[`grund-stierchen__raised-view.jpg`](images/grund-stierchen__raised-view.jpg): Stierchen bridge, Wenzel wall tower and the Alzette weir, from above<br>[`grund-stierchen__detail-tower.jpg`](images/grund-stierchen__detail-tower.jpg): Tower at the Stierchen bridge |
| Wikipedia | [lb: Stierchen](https://lb.wikipedia.org/wiki/Stierchen) |

<a id="saint-esprit-citadel"></a>
### Saint-Esprit Citadel

| | |
|---|---|
| Local name | Citadelle du Saint-Esprit / Plateau du Saint-Esprit |
| OSM name | (not in FEATURED) |
| Coordinates | 49.60715, 6.13578 |
| Category | history |
| About | The Saint-Esprit citadel, built under Vauban in the 1680s on the plateau above the Grund and the Pétrusse, on the site of a former convent. Its massive sloping walls drop to the valley; on top stands the Cité judiciaire, the courts complex built in the style of the old barracks. |
| Images | [`saint-esprit-citadel__exterior.jpg`](images/saint-esprit-citadel__exterior.jpg): The Saint-Esprit citadel walls<br>[`saint-esprit-citadel__plateau.jpg`](images/saint-esprit-citadel__plateau.jpg): The Plateau du Saint-Esprit<br>[`saint-esprit-citadel__from-below.jpg`](images/saint-esprit-citadel__from-below.jpg): The plateau seen from the Grund |
| Wikipedia | [en: Fortress of Luxembourg](https://en.wikipedia.org/wiki/Fortress_of_Luxembourg) |

<a id="fort-obergrunewald"></a>
### Fort Obergrünewald

| | |
|---|---|
| Local name | Fort Obergrünewald |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61528, 6.13756 |
| Category | history |
| About | An 18th-century fort on the Grünewald slope between the Pfaffenthal and the Kirchberg plateau, part of the outer fortress. Low, thick stone walls, ditches and a caponier, partly restored, half hidden among trees above the Alzette. |
| Images | [`fort-obergrunewald__exterior.jpg`](images/fort-obergrunewald__exterior.jpg): The fort above the Alzette<br>[`fort-obergrunewald__walls.jpg`](images/fort-obergrunewald__walls.jpg): Fort walls<br>[`fort-obergrunewald__glacis.jpg`](images/fort-obergrunewald__glacis.jpg): Fort walls and glacis with the old town behind |
| Wikipedia | [en: Fortress of Luxembourg](https://en.wikipedia.org/wiki/Fortress_of_Luxembourg) |

<a id="drai-eechelen"></a>
### Fort Thüngen / Three Acorns Museum

| | |
|---|---|
| Local name | Musée Dräi Eechelen |
| OSM name | `Musée Dräi Eechelen` |
| Coordinates | 49.61639, 6.13930 |
| Category | history |
| About | Fort Thüngen, built by the Austrians from 1732, named after commander Count Thüngen; its three round towers topped by stone acorns give the local name Dräi Eechelen ('three acorns'). Rebuilt in the 1990s–2000s, it houses the fortress and history museum since 2012. Grey-yellow stone towers with conical stone caps and gilt acorn finials, next to Mudam's glass roofs. |
| Images | [`drai-eechelen__aerial.jpg`](images/drai-eechelen__aerial.jpg): Aerial view of Fort Thüngen and Mudam<br>[`drai-eechelen__exterior.jpg`](images/drai-eechelen__exterior.jpg): The three acorn-topped towers<br>[`drai-eechelen__detail-acorn.jpg`](images/drai-eechelen__detail-acorn.jpg): Detail: a stone acorn on the central tower |
| Wikipedia | [en: Fort Thüngen](https://en.wikipedia.org/wiki/Fort_Th%C3%BCngen) |

<a id="neumunster-abbey"></a>
### Neumünster Abbey

| | |
|---|---|
| Local name | Abbaye de Neumünster |
| OSM name | `Centre culturel de rencontre Abbaye de Neumünster` |
| Coordinates | 49.61075, 6.13687 |
| Category | culture |
| About | Benedictine abbey moved to the Grund in the 16th century and rebuilt in the late 17th and early 18th centuries after fires and wars; later a prison (until 1984), it has been a cultural centre since 2004. Long ochre- and cream-plastered wings with grey slate roofs around a large paved courtyard, beside the Alzette and the Saint-Jean church, with the Corniche cliffs above. |
| Images | [`neumunster-abbey__exterior.jpg`](images/neumunster-abbey__exterior.jpg): Abbey buildings in the Grund<br>[`neumunster-abbey__raised-view.jpg`](images/neumunster-abbey__raised-view.jpg): View over the Grund and the abbey at dawn<br>[`neumunster-abbey__courtyard.jpg`](images/neumunster-abbey__courtyard.jpg): Abbey courtyard and buildings |
| Wikipedia | [en: Neumünster Abbey](https://en.wikipedia.org/wiki/Neum%C3%BCnster_Abbey) |

<a id="saint-jean-grund"></a>
### Church of St. John the Baptist, Grund

| | |
|---|---|
| Local name | Église Saint-Jean-Baptiste du Grund |
| OSM name | `Saint-Jean-Baptiste` |
| Coordinates | 49.61063, 6.13619 |
| Category | landmark |
| About | Church of St John the Baptist (Saint-Jean du Grund), the former abbey church of Neumünster, built in the early 18th century. Yellow-plastered walls, a tall slender black spire, and a rich Baroque interior with gilded altars and a Black Madonna. |
| Images | [`saint-jean-grund__interior.jpg`](images/saint-jean-grund__interior.jpg): Interior: nave and baroque high altar<br>[`saint-jean-grund__raised-view.jpg`](images/saint-jean-grund__raised-view.jpg): Grund and the church from above<br>[`saint-jean-grund__tower.jpg`](images/saint-jean-grund__tower.jpg): The church tower |
| Wikipedia | [en: Grund, Luxembourg City](https://en.wikipedia.org/wiki/Grund,_Luxembourg_City) |

<a id="natur-musee"></a>
### National Museum of Natural History

| | |
|---|---|
| Local name | Musée national d'histoire naturelle / Natur Musée |
| OSM name | `Musée national d'histoire naturelle` |
| Coordinates | 49.60970, 6.13560 |
| Category | culture |
| About | National Museum of Natural History, in the former Hospice Saint-Jean in the Grund, beside the Alzette. White-plastered walls, slate roofs and a decorated Baroque stone portal with statues; the building's foundations sit right on the river. |
| Images | [`natur-musee__exterior.jpg`](images/natur-musee__exterior.jpg): Museum in the old Hospice Saint-Jean, Grund<br>[`natur-musee__detail-portal.jpg`](images/natur-musee__detail-portal.jpg): Detail: the old hospice portal<br>[`natur-musee__entrance.jpg`](images/natur-musee__entrance.jpg): Entrance |
| Wikipedia | [en: National Museum of Natural History, Luxembourg](https://en.wikipedia.org/wiki/National_Museum_of_Natural_History,_Luxembourg) |

## Bridges, valleys and parks

<a id="pont-adolphe"></a>
### Adolphe Bridge

| | |
|---|---|
| Local name | Pont Adolphe |
| OSM name | `Pont Adolphe` |
| Coordinates | 49.60844, 6.12688 |
| Category | bridge |
| About | Stone road bridge over the Pétrusse valley, built 1900–1903 to a design by Paul Séjourné; its 85 m main arch was the largest stone arch in the world when finished. Pale sandstone, twin parallel arches joined by a deck, with smaller arches at each end. Renovated 2014–2017, when a suspended pedestrian and cycle deck was added underneath; the tram has crossed it since 2020. |
| Images | [`pont-adolphe__aerial.jpg`](images/pont-adolphe__aerial.jpg): Aerial view of the bridge with Gëlle Fra and Spuerkeess<br>[`pont-adolphe__exterior.jpg`](images/pont-adolphe__exterior.jpg): The bridge after its 2017 renovation, side view<br>[`pont-adolphe__detail-arch.jpg`](images/pont-adolphe__detail-arch.jpg): Detail: the main arch from underneath |
| Wikipedia | [en: Adolphe Bridge](https://en.wikipedia.org/wiki/Adolphe_Bridge) |

<a id="passerelle"></a>
### Passerelle (Old Viaduct)

| | |
|---|---|
| Local name | Passerelle / Viaduc / Al Bréck |
| OSM name | `Pont Viaduc` |
| Coordinates | 49.60583, 6.13361 |
| Category | bridge |
| About | The Old Viaduct (Passerelle, Al Bréck), built 1859–1861 to link the old town with the new railway station across the Pétrusse valley. About 290 m long with 24 sandstone arches, 45 m above the valley. |
| Images | [`passerelle__aerial.jpg`](images/passerelle__aerial.jpg): Aerial view of the Passerelle, Spuerkeess and the Cité judiciaire<br>[`passerelle__exterior.jpg`](images/passerelle__exterior.jpg): The viaduct over the Pétrusse<br>[`passerelle__exterior-2.jpg`](images/passerelle__exterior-2.jpg): Side view of the arches |
| Wikipedia | [en: Passerelle (Luxembourg)](https://en.wikipedia.org/wiki/Passerelle_(Luxembourg)) |

<a id="red-bridge"></a>
### Grand Duchess Charlotte Bridge (Red Bridge)

| | |
|---|---|
| Local name | Pont Grande-Duchesse Charlotte / Roud Bréck |
| OSM name | `Pont Grande-Duchesse Charlotte` |
| Coordinates | 49.61778, 6.13176 |
| Category | bridge |
| About | Steel girder bridge built 1963–1966 (architect Egon Jux) linking the city centre with Kirchberg across the Alzette valley; about 355 m long and 74 m above the valley floor. Painted a strong red, hence the name Roud Bréck; it carries road and, since 2017, the tram, with glass safety screens along the sides. |
| Images | [`red-bridge__aerial.jpg`](images/red-bridge__aerial.jpg): Aerial view of the bridge and Porte de l'Europe<br>[`red-bridge__exterior.jpg`](images/red-bridge__exterior.jpg): Panorama of the red bridge from the fortress<br>[`red-bridge__detail.jpg`](images/red-bridge__detail.jpg): Detail: red steel deck from below |
| Wikipedia | [en: Grand Duchess Charlotte Bridge](https://en.wikipedia.org/wiki/Grand_Duchess_Charlotte_Bridge) |

<a id="clausen-viaduct"></a>
### Clausen railway viaduct

| | |
|---|---|
| Local name | Viaduc de Clausen |
| OSM name | `Clausener Viaduc` |
| Coordinates | 49.61170, 6.14010 |
| Category | bridge |
| About | Stone railway viaduct of the 1860s carrying the line north and east towards Germany across the Alzette valley between Pfaffenthal and Clausen. A long row of tall sandstone arches, now partly wooded around its feet. |
| Images | [`clausen-viaduct__exterior.jpg`](images/clausen-viaduct__exterior.jpg): The viaduct over Clausen<br>[`clausen-viaduct__exterior-2.jpg`](images/clausen-viaduct__exterior-2.jpg): The viaduct arches<br>[`clausen-viaduct__historic.jpg`](images/clausen-viaduct__historic.jpg): Historic photograph of the viaduct |
| Wikipedia | [fr: Viaduc de Clausen](https://fr.wikipedia.org/wiki/Viaduc_de_Clausen) |

<a id="pfaffenthal-lift"></a>
### Pfaffenthal Panoramic Lift

| | |
|---|---|
| Local name | Ascenseur panoramique du Pfaffenthal |
| OSM name | `Panorama-Aufzug Pfaffenthal` |
| Coordinates | 49.61559, 6.13065 |
| Category | viewpoint |
| About | Panoramic glass lift opened in 2016, connecting the Pescatore park in the Ville Haute with the Pfaffenthal about 60–70 m below. A slim steel and glass tower with a footbridge at the top and a glass-floored viewing platform. Free and open late; one of the best views of the Alzette valley and Kirchberg. |
| Images | [`pfaffenthal-lift__exterior.jpg`](images/pfaffenthal-lift__exterior.jpg): The lift, footbridge and the Pfaffenthal<br>[`pfaffenthal-lift__exterior-tower.jpg`](images/pfaffenthal-lift__exterior-tower.jpg): The glass lift shaft<br>[`pfaffenthal-lift__view-from-top.jpg`](images/pfaffenthal-lift__view-from-top.jpg): View towards Kirchberg from the upper platform |
| Wikipedia | [en: Pfaffenthal Panoramic Elevator](https://en.wikipedia.org/wiki/Pfaffenthal_Panoramic_Elevator) |
| Facts for the model | Opened 22 July 2016. A hollow concrete tower 2.6 m square, 74.77 m to the roof, holding the counterweight; the glass shaft on its south side. One cabin, 2.3 m wide and 3.7 m deep, glazed on its face, with a glass floor at the front; 60 m rise in about 30 s (2.5 m/s at most). An enclosed steel through-truss footbridge 72.27 m long, 3 m wide and 3 m tall from the Pescatore park, running 9 m past the shaft to a glass-walled viewing platform with a small glass floor. Open daily 05:45 to 01:00; closed for maintenance from 09:00 on the first Monday of the month. Sources: [Wikipedia](https://en.wikipedia.org/wiki/Pfaffenthal_Panoramic_Elevator), [vdl.lu](https://www.vdl.lu/en/node/8761). Used by `pipeline/events/lift_model.py`. |

<a id="petrusse-valley"></a>
### Pétrusse Valley

| | |
|---|---|
| Local name | Vallée de la Pétrusse |
| OSM name | `Vallée de la Pétrusse` |
| Coordinates | 49.60562, 6.12932 |
| Category | park |
| About | The deep, green valley of the small Pétrusse river separating the old town from the Gare quarter, spanned by the Pont Adolphe and the Passerelle. Parks and paths along the bottom, sandstone cliffs and fortress walls on the north side; the river was renaturalised in the 2020s. |
| Images | [`petrusse-valley__panorama.jpg`](images/petrusse-valley__panorama.jpg): Panorama of the valley<br>[`petrusse-valley__aerial.jpg`](images/petrusse-valley__aerial.jpg): Aerial view over the valley with Spuerkeess and Pont Adolphe<br>[`petrusse-valley__fortress-walls.jpg`](images/petrusse-valley__fortress-walls.jpg): Fortress walls in the valley |
| Wikipedia | [en: Pétrusse](https://en.wikipedia.org/wiki/P%C3%A9trusse) |

<a id="municipal-park"></a>
### Municipal Park

| | |
|---|---|
| Local name | Parc municipal Édouard André / Stadtpark |
| OSM name | `Parc municipal Edouard André` |
| Coordinates | 49.61334, 6.12544 |
| Category | park |
| About | Laid out from 1871 by French landscape architect Édouard André on the ground freed by the dismantling of the fortress, forming a green belt around the west of the old town. Winding paths, large trees, lawns and playgrounds; Villa Vauban stands in it. |
| Images | [`municipal-park__park.jpg`](images/municipal-park__park.jpg): Park paths and lawns<br>[`municipal-park__plan.jpg`](images/municipal-park__plan.jpg): Édouard André's 1871 plan of the park<br>[`municipal-park__detail-fountain.jpg`](images/municipal-park__detail-fountain.jpg): Detail: drinking fountain |
| Wikipedia | [en: Édouard André Municipal Park](https://en.wikipedia.org/wiki/%C3%89douard_Andr%C3%A9_Municipal_Park) |

<a id="villa-vauban"></a>
### Villa Vauban

| | |
|---|---|
| Local name | Villa Vauban – Musée d'Art de la Ville |
| OSM name | `Villa Vauban` |
| Coordinates | 49.61311, 6.12249 |
| Category | culture |
| About | A 19th-century villa built in 1873 on the remains of a Vauban fortification in the Municipal Park; the city's art museum since 1959, extended with a modern bronze-coloured wing in 2010. White façade, mansard slate roof, lawns and a fountain in front. |
| Images | [`villa-vauban__exterior.jpg`](images/villa-vauban__exterior.jpg): The villa in its park<br>[`villa-vauban__exterior-park.jpg`](images/villa-vauban__exterior-park.jpg): Villa seen from the park<br>[`villa-vauban__facade.jpg`](images/villa-vauban__facade.jpg): Façade |
| Wikipedia | [en: Villa Vauban](https://en.wikipedia.org/wiki/Villa_Vauban) |

## Gare quarter

<a id="spuerkeess-tower"></a>
### Spuerkeess (BCEE) headquarters and clock tower

| | |
|---|---|
| Local name | Banque et Caisse d'Épargne de l'État |
| OSM name | `BCEE Clock Tower` |
| Coordinates | 49.60743, 6.12857 |
| Category | landmark |
| About | Headquarters of the state savings bank (BCEE / Spuerkeess) on Place de Metz, built 1909–1913 by architect Jean-Pierre Koenig in a neo-Gothic and eclectic style. The landmark is its tall clock tower with a green copper spire, seen from the Pont Adolphe and the Pétrusse valley. Pale grey-yellow stone, steep slate roofs, carved ornament. |
| Images | [`spuerkeess-tower__aerial.jpg`](images/spuerkeess-tower__aerial.jpg): Aerial view of the Spuerkeess headquarters and Pont Adolphe<br>[`spuerkeess-tower__exterior.jpg`](images/spuerkeess-tower__exterior.jpg): Headquarters on Place de Metz<br>[`spuerkeess-tower__tower.jpg`](images/spuerkeess-tower__tower.jpg): The clock tower<br>[`spuerkeess-tower__detail-ornament.jpg`](images/spuerkeess-tower__detail-ornament.jpg): Detail: façade ornament |
| Wikipedia | [fr: Banque et caisse d'épargne de l'État](https://fr.wikipedia.org/wiki/Banque_et_caisse_d'%C3%A9pargne_de_l'%C3%89tat) |

<a id="gare-centrale"></a>
### Luxembourg railway station

| | |
|---|---|
| Local name | Gare de Luxembourg |
| OSM name | `Gare Centrale` |
| Coordinates | 49.59995, 6.13352 |
| Category | transport |
| About | The main station building dates from 1907–1913, in a neo-Baroque style with a tall clock tower and a large arched main window. Cream sandstone with grey slate roofs and dark-green metal details; a modern glass entrance hall was added in front in the 2010s. Tram terminus and bus hub on the Place de la Gare. |
| Images | [`gare-centrale__exterior.jpg`](images/gare-centrale__exterior.jpg): Station building over Place de la Gare<br>[`gare-centrale__glass-entrance.jpg`](images/gare-centrale__glass-entrance.jpg): Modern glass entrance hall<br>[`gare-centrale__tracks.jpg`](images/gare-centrale__tracks.jpg): Overview of the tracks from the road bridge |
| Wikipedia | [en: Luxembourg railway station](https://en.wikipedia.org/wiki/Luxembourg_railway_station) |

## Kirchberg

<a id="pfaffenthal-kirchberg-station"></a>
### Pfaffenthal-Kirchberg station and funicular

| | |
|---|---|
| Local name | Gare Pfaffenthal-Kirchberg |
| OSM name | `Pfaffenthal-Kirchberg` |
| Coordinates | 49.61895, 6.13293 |
| Category | transport |
| About | Railway station opened in 2017 in the Alzette valley below the Red Bridge, linked to the tram stop on the bridge by a funicular and a lift. Modern concrete, glass and steel, with a long sloping funicular track up the valley side. |
| Images | [`pfaffenthal-kirchberg-station__platform.jpg`](images/pfaffenthal-kirchberg-station__platform.jpg): Platform with a double-deck train<br>[`pfaffenthal-kirchberg-station__raised-view.jpg`](images/pfaffenthal-kirchberg-station__raised-view.jpg): Station and funicular from above<br>[`pfaffenthal-kirchberg-station__from-bridge.jpg`](images/pfaffenthal-kirchberg-station__from-bridge.jpg): Station seen from the Red Bridge |
| Wikipedia | [en: Pfaffenthal-Kirchberg railway station](https://en.wikipedia.org/wiki/Pfaffenthal-Kirchberg_railway_station) |

<a id="kirchberg-towers"></a>
### Porte de l'Europe and Kirchberg towers

| | |
|---|---|
| Local name | Porte de l'Europe / Tours Kirchberg |
| OSM name | (not in FEATURED) |
| Coordinates | 49.61948, 6.14330 |
| Category | landmark |
| About | The Porte de l'Europe: twin office towers by Ricardo Bofill's Taller de Arquitectura at the Kirchberg end of the Red Bridge, forming a gateway to the European quarter. Tall, slim towers with pale stone-coloured grid façades and glass. |
| Images | [`kirchberg-towers__aerial.jpg`](images/kirchberg-towers__aerial.jpg): Aerial view of the Porte de l'Europe towers and the Red Bridge<br>[`kirchberg-towers__exterior.jpg`](images/kirchberg-towers__exterior.jpg): The Porte de l'Europe towers<br>[`kirchberg-towers__panorama.jpg`](images/kirchberg-towers__panorama.jpg): Panorama of the Kirchberg gateway |
| Wikipedia | [lb: Porte de l'Europe](https://lb.wikipedia.org/wiki/Porte_de_l'Europe) |

<a id="philharmonie"></a>
### Philharmonie Luxembourg

| | |
|---|---|
| Local name | Philharmonie Luxembourg |
| OSM name | `Philharmonie Luxembourg` |
| Coordinates | 49.61845, 6.14253 |
| Category | culture |
| About | Concert hall on Place de l'Europe by Christian de Portzamparc, opened 2005. An eye-shaped (elliptical) building wrapped in a screen of 823 thin white steel columns, with the main 1,500-seat hall inside. Bright white against the glass towers of Kirchberg. |
| Images | [`philharmonie__aerial.jpg`](images/philharmonie__aerial.jpg): Aerial view of the Kirchberg with the Philharmonie and the Court of Justice<br>[`philharmonie__exterior.jpg`](images/philharmonie__exterior.jpg): Exterior with the columned façade<br>[`philharmonie__detail-columns.jpg`](images/philharmonie__detail-columns.jpg): Detail: the white steel columns<br>[`philharmonie__interior.jpg`](images/philharmonie__interior.jpg): Interior: main concert hall |
| Wikipedia | [en: Philharmonie Luxembourg](https://en.wikipedia.org/wiki/Philharmonie_Luxembourg) |

<a id="mudam"></a>
### Mudam (Grand Duke Jean Museum of Modern Art)

| | |
|---|---|
| Local name | Musée d'Art Moderne Grand-Duc Jean |
| OSM name | `MUDAM` |
| Coordinates | 49.61682, 6.14003 |
| Category | culture |
| About | Museum of modern art by I. M. Pei, opened 2006, built on the foundations of Fort Thüngen's walls. Warm honey-coloured French limestone, faceted glass roofs and a central glass pyramid-like hall that echoes the fortress geometry. |
| Images | [`mudam__aerial.jpg`](images/mudam__aerial.jpg): Aerial view of Mudam and Fort Thüngen<br>[`mudam__exterior.jpg`](images/mudam__exterior.jpg): Exterior on a winter day<br>[`mudam__entrance.jpg`](images/mudam__entrance.jpg): Entrance with visitors |
| Wikipedia | [en: MUDAM](https://en.wikipedia.org/wiki/MUDAM) |

<a id="cjeu-towers"></a>
### Court of Justice of the European Union

| | |
|---|---|
| Local name | Cour de justice de l'Union européenne |
| OSM name | `Cour de Justice Tower Rocca` |
| Coordinates | 49.62228, 6.14437 |
| Category | landmark |
| About | Court of Justice of the European Union. The original Palais (1973) has been extended several times, notably by Dominique Perrault, whose two gold-clad towers (2008) and third tower (2019) dominate the Kirchberg plateau. The towers and the Palais' ring are wrapped in bronze-gold anodised metal mesh. |
| Images | [`cjeu-towers__aerial.jpg`](images/cjeu-towers__aerial.jpg): Aerial view of the Court of Justice complex and Porte de l'Europe<br>[`cjeu-towers__towers.jpg`](images/cjeu-towers__towers.jpg): The golden towers<br>[`cjeu-towers__entrance.jpg`](images/cjeu-towers__entrance.jpg): Entrance area of the Palais<br>[`cjeu-towers__interior.jpg`](images/cjeu-towers__interior.jpg): Interior: grand courtroom |
| Wikipedia | [en: Court of Justice of the European Union](https://en.wikipedia.org/wiki/Court_of_Justice_of_the_European_Union) |

<a id="european-parliament-kad"></a>
### European Parliament, Konrad Adenauer Building

| | |
|---|---|
| Local name | Bâtiment Konrad Adenauer |
| OSM name | `Parlement européen - bâtiment Konrad Adenauer (KAD)` |
| Coordinates | 49.62179, 6.14656 |
| Category | landmark |
| About | The European Parliament's General Secretariat building in Kirchberg. The original 1970s building has been replaced by a large new complex completed in phases in the 2010s–2020s. Glass and metal façades in silver and grey with red window panels on parts of the older wings. |
| Images | [`european-parliament-kad__exterior.jpg`](images/european-parliament-kad__exterior.jpg): The new Konrad Adenauer building<br>[`european-parliament-kad__exterior-2.jpg`](images/european-parliament-kad__exterior-2.jpg): Façade detail of the building |
| Wikipedia | [en: European Parliament in Luxembourg](https://en.wikipedia.org/wiki/European_Parliament_in_Luxembourg) |

<a id="coque"></a>
### d'Coque

| | |
|---|---|
| Local name | Centre national sportif et culturel d'Coque |
| OSM name | `Centre National Sportif et Culturel d'Coque` |
| Coordinates | 49.62352, 6.15324 |
| Category | culture |
| About | The national sports and cultural centre by architect Roger Taillibert, opened 2002: an arena and Olympic swimming pool under one huge, low, shell-shaped roof (the 'coque'). The roof reads as a grey-blue curved dome in the Kirchberg landscape. See the freedom-of-panorama note: free photos are scarce. |
| Images | [`coque__avenue.jpg`](images/coque__avenue.jpg): Avenue John F. Kennedy with the edge of the shell roof<br>[`coque__tram-stop.jpg`](images/coque__tram-stop.jpg): Coque tram stop (building partly blurred on Commons) |
| Wikipedia | [en: D'Coque](https://en.wikipedia.org/wiki/D'Coque) |

<a id="kirchberg-parc-central"></a>
### Kirchberg Central Park (Arboretum)

| | |
|---|---|
| Local name | Parc Central, Arboretum du Kirchberg |
| OSM name | `Arboretum Kirchberg Parc Central` |
| Coordinates | 49.62577, 6.15612 |
| Category | park |
| About | The central park of Kirchberg, part of the Kirchberg arboretum, laid out by landscape architect Peter Latz around d'Coque. Lawns, groves and straight paths with modern sculpture; d'Coque's roof and the Kirchberg towers form the backdrop. |
| Images | [`kirchberg-parc-central__park.jpg`](images/kirchberg-parc-central__park.jpg): The park with d'Coque behind<br>[`kirchberg-parc-central__park-2.jpg`](images/kirchberg-parc-central__park-2.jpg): Park paths |
| Wikipedia | [fr: Arboretum du Kirchberg](https://fr.wikipedia.org/wiki/Arboretum_du_Kirchberg) |

<a id="university-kirchberg"></a>
### University of Luxembourg, Kirchberg campus

| | |
|---|---|
| Local name | Université du Luxembourg – Campus Kirchberg |
| OSM name | `Université du Luxembourg - Campus Kirchberg` |
| Coordinates | 49.62646, 6.15926 |
| Category | landmark |
| About | The University of Luxembourg's Kirchberg campus, home to parts of its faculty and research units in modern office-style buildings along the Avenue John F. Kennedy area. The university's main campus is now at Belval (Esch-sur-Alzette). |
| Images | [`university-kirchberg__aerial.jpg`](images/university-kirchberg__aerial.jpg): Aerial shot of lower Kirchberg with the campus |
| Wikipedia | [en: University of Luxembourg](https://en.wikipedia.org/wiki/University_of_Luxembourg) |

<a id="kirchberg-shopping-center"></a>
### Auchan Kirchberg shopping centre

| | |
|---|---|
| Local name | Kirchberg Shopping Center |
| OSM name | `Kirchberg Shopping Center` |
| Coordinates | 49.63330, 6.16936 |
| Category | landmark |
| About | The shopping centre with an Auchan hypermarket and shops at the eastern end of the Kirchberg plateau, opened in the 1990s, next to the Kinepolis cinema. Modern glass, metal and concrete with a glass-roofed atrium inside. |
| Images | [`kirchberg-shopping-center__exterior.jpg`](images/kirchberg-shopping-center__exterior.jpg): Entrance on Avenue John F. Kennedy<br>[`kirchberg-shopping-center__interior.jpg`](images/kirchberg-shopping-center__interior.jpg): Interior mall |
| Wikipedia | [en: Kirchberg, Luxembourg](https://en.wikipedia.org/wiki/Kirchberg,_Luxembourg) |

## Citywide additions

82 further landmarks across the quarters inside the painted map, added November 2026. Each section also has Quarter, Facts, Visiting, Sources, Pin (map label · rank, 1 = most important) and Model rows, read by `pipeline/build_landmarks.py` and `pipeline/build_places.py`. Texts are original summaries; the sources they draw on are linked in each section. Coordinates come from OpenStreetMap (the project's OSM extract or Nominatim) or, where OSM has no point, from Wikidata. Photos: one per landmark (two for the most important), Commons thumbnails ~1200 px, credited in `sources.json`.

Index: **Ville Haute**: [Grand Duchess Charlotte Monument](#charlotte-monument), [Ministry of Foreign and European Affairs](#foreign-ministry), [Villa Louvigny](#villa-louvigny), [Théâtre des Capucins](#theatre-des-capucins), [Lëtzebuerg City Library](#city-library), [Trinity Church](#trinity-church), [Council of State Building](#council-of-state), [Luxembourg Synagogue](#synagogue), [National Archives of Luxembourg (Plateau du Saint-Esprit)](#national-archives), [Old Athénée (former National Library)](#old-athenee), [Cinémathèque of the City of Luxembourg](#cinematheque), [Hôtel de Bourgogne](#hotel-de-bourgogne), [Central Post Office](#central-post-office), [Lambert Redoubt](#fort-lambert), [Cité judiciaire](#cite-judiciaire), [Dicks-Lentz Monument](#dicks-lentz-monument), [Badanstalt City Baths](#bains-du-centre), [Refuge Saint-Maximin](#hotel-saint-maximin), [Central Bank of Luxembourg](#central-bank), [National Monument of Luxembourg Solidarity](#solidarity-monument), [Saint-Alphonse Church](#saint-alphonse), [Hämmelsmarsch Fountain](#hammelsmarsch-fountain), [Maison de Raville](#maison-de-raville) · **Bock**: [Castle Bridge](#castle-bridge), [Hollow Tooth](#dent-creuse) · **Grund**: [Rham Plateau](#rham-plateau) · **Pétrusse valley**: [Saint-Quirin Chapel](#saint-quirin) · **Gare**: [Place de Paris](#place-de-paris), [Villa Pauly](#villa-pauly), [ARBED Building](#arbed-building), [Publications Office of the European Union](#publications-office), [Sacred Heart Church](#sacre-coeur) · **Bonnevoie**: [Rotondes](#rotondes), [Banannefabrik](#banannefabrik) · **Hollerich**: [Den Atelier](#den-atelier) · **Verlorenkost**: [Stade Achille Hammerel](#stade-hammerel) · **Limpertsberg**: [Grand Théâtre de Luxembourg](#grand-theatre), [Lycée Robert-Schuman](#lycee-robert-schuman), [Ciné Utopia](#cine-utopia), [Mausoleum of the French Soldiers](#french-mausoleum), [Robert Schuman Monument](#schuman-monument), [Lycée des Arts et Métiers](#lycee-arts-et-metiers), [Russian Orthodox Church of Saints Peter and Paul](#orthodox-church), [Glacis](#glacis), [Lycée technique du Centre](#lycee-technique-centre), [Notre-Dame Cemetery](#notre-dame-cemetery), [Glacis Chapel](#glacis-chapel), [Saint-Joseph Church, Limpertsberg](#saint-joseph), [Fondation J.-P. Pescatore](#fondation-pescatore), [National Monument of Resistance and Deportation](#hinzert-cross) · **Pfaffenthal**: [Saint-Mathieu Church, Pfaffenthal](#saint-mathieu), [Vauban Towers](#vauban-towers), [Eich Gate and Pfaffenthal wall](#pfaffenthal-gates), [Fort Niedergrünewald](#fort-niedergrunewald), [Pfaffenthal Viaduct](#pfaffenthal-viaduct) · **Clausen**: [Fort Rubamprez](#fort-rubamprez), [La Fontaine Castle ruins and Mansfeld Park](#mansfeld-castle), [Sportlycée](#sport-lycee), [Malakoff Tower](#malakoff-tower), [Fort Rumigny](#fort-rumigny), [Rives de Clausen](#rives-de-clausen), [Saint Cunigunde Church, Clausen](#sainte-cunegonde) · **Kirchberg**: [European Court of Auditors](#court-of-auditors), [National Library of Luxembourg](#national-library), [Chamber of Commerce](#chamber-of-commerce), [Fort Parkhöhe](#fort-parkhohe), [European Investment Bank](#eib), [European School Luxembourg I](#european-school), [Fort Olizy](#fort-olizy), [Jean Monnet 2 Building](#jean-monnet-2), [Kinepolis Kirchberg](#kinepolis), [Robert Schuman Building](#schuman-building), [European Convention Center Luxembourg](#hemicycle), [Luxexpo The Box](#luxexpo) · **Weimerskirch**: [Saint-Martin Church, Weimerskirch](#weimerskirch-church) · **Dommeldange**: [Saint-Hubert Church, Dommeldange](#dommeldange-church) · **Pulvermühl**: [Pulvermühl Viaduct](#pulvermuhl-viaduct) · **Hamm**: [Schläifmillen](#schlaifmillen), [Church of the Exaltation of the Holy Cross, Hamm](#hamm-church) · **Cents**: [Holy Spirit Church, Cents](#cents-church), [Fort Dumoulin](#fort-dumoulin) · **Neudorf**: [Saint-Henri Church, Neudorf](#neudorf-church)

<a id="charlotte-monument"></a>
### Grand Duchess Charlotte Monument

| | |
|---|---|
| Local name | Monument Grande-Duchesse Charlotte / Groussherzogin-Charlotte-Monument |
| Coordinates | 49.60985, 6.13245 |
| Category | landmark |
| Quarter | Ville Haute |
| About | This bronze figure on Place Clairefontaine honours Grand Duchess Charlotte, who reigned from 1919 to 1964 and whose wartime radio broadcasts from exile made her a symbol of Luxembourg's independence. The Parisian sculptor Jean Cardot designed it, and it was unveiled in 1990 in the presence of the grand-ducal family. The simplified figure stands wrapped in a long cloak, one arm raised with the palm turned upwards, on a low round plinth in the middle of the square. |
| Facts | Unveiled: 29 April 1990<br>Sculptor: Jean Cardot<br>Material: bronze<br>Height: 2.75 m<br>Cast by: Fonderie de Coubertin |
| Visiting | Open-air monument on a public square, accessible at all times. |
| Images | [`charlotte-monument__photo.jpg`](images/charlotte-monument__photo.jpg): Grand Duchess Charlotte Monument |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Denkmal_der_Gro%C3%9Fherzogin_Charlotte) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Denkmal_der_Gro%C3%9Fherzogin_Charlotte) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Groussherzogin-Charlotte-Monument_%28Stad_L%C3%ABtzebuerg%29) |
| Pin | Charlotte Monument · 2 |
| Model | no |

<a id="foreign-ministry"></a>
### Ministry of Foreign and European Affairs

| | |
|---|---|
| Local name | Ministère des Affaires étrangères et européennes / Bâtiment Mansfeld |
| Coordinates | 49.61221, 6.13319 |
| Category | government |
| Quarter | Ville Haute |
| About | Luxembourg's foreign ministry works from the restored Mansfeld building on Rue du Palais de Justice, a manor house that served as the residence of the Spanish-era governors in the 16th century and briefly lodged Louis XIV in 1687. From the 1790s until 2008 it was the city's courthouse, which gave the street its name. After a four-year restoration the ministry moved in around 2017, and the old house keeps painted walls, fireplaces and a 19th-century wooden staircase under a steep timber-framed roof. |
| Facts | Origins: 16th-century manor house<br>Former uses: governor's residence; courthouse (1790s-2008)<br>Restoration: about 2013-2017<br>Use: Ministry of Foreign and European Affairs<br>Address: 9 rue du Palais de Justice |
| Visiting | Government offices; the interior is not normally open to the public, apart from occasional heritage days. |
| Images | [`foreign-ministry__photo.jpg`](images/foreign-ministry__photo.jpg): Ministry of Foreign and European Affairs |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Minist%C3%A8re_des_Affaires_%C3%A9trang%C3%A8res_et_europ%C3%A9ennes) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Minist%C3%A8re_des_Affaires_%C3%A9trang%C3%A8res_et_europ%C3%A9ennes) · [Paperjam](https://paperjam.lu/article/batiment-mansfeld-restaure) · [Official site](https://maee.gouvernement.lu/) |
| Pin | Foreign Ministry · 3 |

<a id="villa-louvigny"></a>
### Villa Louvigny

| | |
|---|---|
| Local name | Villa Louvigny |
| Coordinates | 49.61118, 6.12262 |
| Category | landmark |
| Quarter | Ville Haute |
| About | Villa Louvigny stands in the Municipal Park on the site of the old Fort Louvigny, named after the Count of Louvigny, who ran the fortress works in the 1670s. Built around 1920, it was rented and then bought by the Luxembourg broadcasting company, forerunner of RTL, which turned it into radio studios by 1939 and later hosted the Eurovision Song Contest here in 1962 and 1966. Broadcasting left for Kirchberg in the 1990s, and since 2000 the large, pale building among the park's trees has been the main seat of the Ministry of Health. |
| Facts | Built: around 1920<br>Converted to studios: 1936-1939<br>Former use: headquarters of Radio Luxembourg / CLT<br>Eurovision hosts: 1962 and 1966<br>Use: Ministry of Health (since 2000)<br>Heritage status: national monument |
| Visiting | Government offices; seen from the paths of the Municipal Park. |
| Images | [`villa-louvigny__photo.jpg`](images/villa-louvigny__photo.jpg): Villa Louvigny<br>[`villa-louvigny__photo-2.jpg`](images/villa-louvigny__photo-2.jpg): Villa Louvigny from the municipal park |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Villa_Louvigny) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Villa_Louvigny) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Villa_Louvigny) |
| Pin | Villa Louvigny · 1 |

<a id="theatre-des-capucins"></a>
### Théâtre des Capucins

| | |
|---|---|
| Local name | Théâtre des Capucins / Kapuzinertheater |
| Coordinates | 49.61260, 6.13016 |
| Category | culture |
| Quarter | Ville Haute |
| About | This intimate theatre in the old town occupies buildings put up in 1623 for a Capuchin friary, which survived until 1795. During the French Revolutionary period the convent became an arms depot and grain store, and from 1869 to 1964 its former church served as the city's main theatre. After renovation it reopened in 1985 with a hall of about 270 seats and is now run together with the Grand Théâtre, staging plays in Luxembourgish, French and German. |
| Facts | Built: 1623, as a Capuchin friary<br>Theatre use: 1869-1964, reopened 1985<br>Capacity: about 270 seats<br>Operator: Théâtres de la Ville de Luxembourg<br>Use: drama theatre |
| Visiting | Open for performances; see the Théâtres de la Ville de Luxembourg programme. |
| Images | [`theatre-des-capucins__photo.jpg`](images/theatre-des-capucins__photo.jpg): Théâtre des Capucins |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Th%C3%A9%C3%A2tre_des_Capucins) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Th%C3%A9%C3%A2tre_des_Capucins) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Th%C3%A9%C3%A2tre_des_Capucins) · [Official site](http://www.theatres.lu/) |
| Pin | Théâtre des Capucins · 3 |

<a id="city-library"></a>
### Lëtzebuerg City Library

| | |
|---|---|
| Local name | Lëtzebuerg City Bibliothèque |
| Coordinates | 49.61169, 6.13013 |
| Category | culture |
| Quarter | Ville Haute |
| About | The city's public lending library sits in the Cité cultural building on Rue Génistre, a few steps from Place d'Armes, in what was once the Ciné Cité cinema. Founded in 1967 with a gift of books from the National Library, it moved several times before opening here in September 2008 after a conversion. Reading areas fill the ground floor with shelves on two levels below, and the upper floors hold a lounge bar and a conference room; the library took its present name in 2024. |
| Facts | Founded: 1967<br>Current premises: opened 2008, renovated 2018<br>Former name: Cité Bibliothèque (2008-2024)<br>Building: former Ciné Cité, Rue Génistre<br>Use: municipal public library |
| Visiting | Public library, free to enter during opening hours. |
| Images | [`city-library__photo.jpg`](images/city-library__photo.jpg): Lëtzebuerg City Library |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/L%C3%ABtzebuerg_City_Biblioth%C3%A8que) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/L%C3%ABtzebuerg_City_Biblioth%C3%A8que) · [Official site](https://citybiblio.lu) |
| Pin | City Library · 3 |
| Interior | none |

<a id="trinity-church"></a>
### Trinity Church

| | |
|---|---|
| Local name | Église protestante de la Trinité / Dräifaltegkeetskierch |
| Coordinates | 49.60907, 6.13243 |
| Category | church |
| Quarter | Ville Haute |
| About | A chapel stood on this spot on Rue de la Congrégation from the 14th century, later passing to the Dominicans and then, in 1628, to the Canonesses of Notre-Dame, who ran a girls' school. Their church was wrecked in the French siege of 1684; its replacement, begun in 1737 and consecrated in 1745, was the city's first large Baroque building. Under Prussian garrison rule it was handed to the Protestants, and it remains the country's main Protestant church. |
| Facts | Built: 1737-1745<br>Style: Baroque<br>Consecrated: 1745, to the Holy Trinity<br>Protestant use: since the early 19th century (garrison church for Prussian troops)<br>Use: Protestant church |
| Visiting | Open to the public during services and church events. |
| Images | [`trinity-church__photo.jpg`](images/trinity-church__photo.jpg): Trinity Church |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Trinity_Church%2C_Luxembourg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Trinity_Church%2C_Luxembourg) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/%C3%89glise_de_la_Trinit%C3%A9_de_Luxembourg) |
| Pin | Trinity Church · 2 |

<a id="council-of-state"></a>
### Council of State Building

| | |
|---|---|
| Local name | Hôtel du Conseil d'État / Staatsrot |
| Coordinates | 49.61153, 6.13493 |
| Category | government |
| Quarter | Ville Haute |
| About | The seat of the Council of State, Luxembourg's advisory body on legislation, stands at the corner of Rue Sigefroi and Boulevard Victor Thorn, where the Villa Werling once stood. The state bought and demolished the villa after the Second World War, and a new building by Constant Gillardin went up in its place, opening in January 1960. Its design deliberately blends modern architecture with features of the old houses of the nearby Fish Market, and a tower on the north side screens a neighbouring building. |
| Facts | Opened: 28 January 1960<br>Architect: Constant Gillardin (under Hubert Schumacher)<br>Use: seat of the Council of State<br>Location: corner of Rue Sigefroi and Boulevard Victor Thorn |
| Visiting | Outside only. |
| Images | [`council-of-state__photo.jpg`](images/council-of-state__photo.jpg): Council of State Building |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Staatsrot_%28Gebai%29) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Staatsrot_%28Gebai%29) |
| Pin | Council of State · 3 |

<a id="synagogue"></a>
### Luxembourg Synagogue

| | |
|---|---|
| Local name | Synagogue de Luxembourg / Synagog Stad Lëtzebuerg |
| Coordinates | 49.60965, 6.12164 |
| Category | religion |
| Quarter | Ville Haute |
| About | The city's main synagogue on Avenue Monterey replaced the Moorish Revival synagogue of 1894 near Rue Notre-Dame, which the Nazi occupiers desecrated in 1941 and pulled down by 1943. Work on the new building began in 1951 to plans by Victor Engels and René Mailliet, and it was consecrated in June 1953 in the presence of Grand Duke Jean. Its stained-glass windows are the work of Frantz Kinnen. |
| Facts | Built: 1951-1953<br>Consecrated: 28 June 1953<br>Architects: Victor Engels and René Mailliet<br>Windows: Frantz Kinnen<br>Use: Orthodox Jewish synagogue |
| Visiting | A place of worship; visits by arrangement with the Jewish community. |
| Images | [`synagogue__photo.jpg`](images/synagogue__photo.jpg): Luxembourg Synagogue |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Luxembourg_Synagogue) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Luxembourg_Synagogue) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Synagogue_de_Luxembourg) · [Official site](https://synagogue.lu/) |
| Pin | Synagogue · 2 |

<a id="national-archives"></a>
### National Archives of Luxembourg (Plateau du Saint-Esprit)

| | |
|---|---|
| Local name | Archives nationales de Luxembourg / Nationalarchiven |
| Coordinates | 49.60831, 6.13445 |
| Category | culture |
| Quarter | Ville Haute |
| About | From 1968 the National Archives, keepers of the country's political, religious and economic records, occupied the former barracks of the Volunteer Company on the Plateau du Saint-Esprit, a building first put up as a military hospital. In 2026 the archives moved to a new building at Belval in Esch-sur-Alzette, designed by Paul Bretz, leaving this historic block above the Pétrusse valley. |
| Facts | Archives here: 1968-2026<br>Original use: military hospital, later barracks of the Volunteer Company<br>Institution: state cultural institute under the Ministry of Culture<br>New home: Belval, Esch-sur-Alzette (2026) |
| Visiting | Outside only. |
| Images | [`national-archives__photo.jpg`](images/national-archives__photo.jpg): National Archives of Luxembourg (Plateau du Saint-Esprit) |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/L%C3%ABtzebuerger_Nationalarchiven) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/L%C3%ABtzebuerger_Nationalarchiven) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Archives_nationales_de_Luxembourg) · [Official site](https://anlux.gouvernement.lu/en/service.html) |
| Pin | Old National Archives · 3 |

<a id="old-athenee"></a>
### Old Athénée (former National Library)

| | |
|---|---|
| Local name | Ancien Athénée / Al Nationalbibliothéik |
| Coordinates | 49.60956, 6.13083 |
| Category | education |
| Quarter | Ville Haute |
| About | This long block on Boulevard Roosevelt, next to the cathedral, grew out of the Jesuit college founded in 1603, whose church is now Notre-Dame Cathedral. After the Jesuits it housed the Athénée, the country's oldest secondary school, until the school moved to new premises in 1964. From 1973 the National Library used the restored building, until it moved to Kirchberg in 2019. The state now plans to convert it for court and other public offices, with public space on the ground floor. |
| Facts | Founded: 1603, as the Jesuit college<br>Athénée school here: until 1964<br>National Library: 1973-2019<br>Planned use: commercial chambers of the District Court and other public offices |
| Visiting | Outside only; the building has been closed since the library left. |
| Wikipedia | [Wikipedia (en): Athénée de Luxembourg](https://en.wikipedia.org/wiki/Ath%C3%A9n%C3%A9e_de_Luxembourg) |
| Sources | [Wikipedia (en): Athénée de Luxembourg](https://en.wikipedia.org/wiki/Ath%C3%A9n%C3%A9e_de_Luxembourg) · [National Library of Luxembourg](https://bnl.public.lu/dam-assets/publications/presentation/2023-entrez-et-dcouvrez.pdf) · [DP: future of the former Athénée buildings](https://dp.lu/what-will-be-the-future-of-the-former-buildings-of-the-athenee-de-luxembourg/?lang=en) |
| Pin | Old Athénée · 2 |

<a id="cinematheque"></a>
### Cinémathèque of the City of Luxembourg

| | |
|---|---|
| Local name | Cinémathèque de la Ville de Luxembourg / Stater Cinemathéik |
| Coordinates | 49.61315, 6.13078 |
| Category | culture |
| Quarter | Ville Haute |
| About | The city's film archive and repertory cinema screens in the former Ciné Vox on Place du Théâtre, the only cinema in the Ville Haute. Founded by Fred Junck in the mid-1970s and taken over by the city in 1977, it holds more than 13,000 films and is strong on film noir, classic Hollywood and French cinema of the 1930s and 1940s. The building is due for a four-year renovation and extension from 2026, with screenings moving next door to the Théâtre des Capucins in the meantime. |
| Facts | Founded: 1975 by Fred Junck; city service since 1977<br>Collection: more than 13,000 films<br>Building: former Ciné Vox, Place du Théâtre<br>Use: film archive and repertory cinema |
| Visiting | Public screenings most days; during the renovation from 2026 screenings move to the Théâtre des Capucins. |
| Images | [`cinematheque__photo.jpg`](images/cinematheque__photo.jpg): Cinémathèque of the City of Luxembourg |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Cin%C3%A9math%C3%A8que_de_la_Ville_de_Luxembourg) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Cin%C3%A9math%C3%A8que_de_la_Ville_de_Luxembourg) · [City of Luxembourg](https://vdl.lu/en/news/renovation-and-extension-luxembourg-city-cinematheque) · [Luxembourg City Tourist Office](https://www.luxembourg-city.com/en/place/cinema/cinematheque-film-library-luxembourg) |
| Pin | Cinémathèque · 3 |

<a id="hotel-de-bourgogne"></a>
### Hôtel de Bourgogne

| | |
|---|---|
| Local name | Hôtel de Bourgogne / Maison de Bourgogne |
| Coordinates | 49.60958, 6.13207 |
| Category | government |
| Quarter | Ville Haute |
| About | One of the oldest surviving houses in the city, the Hôtel de Bourgogne is first recorded in 1447 on ground once used by the counts of Luxembourg for minting coins. It soon belonged to Claude de Neufchâtel, governor of the duchy in the late 15th century, and later passed through several noble families and the Congregation of Notre-Dame. From 1975 to 2019 it housed the Ministry of State, the Prime Minister's office. Its stair tower still shows brick columns and pointed arches from the shift between Gothic and Renaissance. |
| Facts | First recorded: 1447<br>Address: 4 rue de la Congrégation<br>Style: late Gothic to Renaissance<br>Use: Ministry of State (Prime Minister's office), 1975-2019<br>Earlier names: Maison du Fay, Berbourg, Metternich |
| Visiting | Government building; seen from outside only. |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Minist%C3%A8re_d%27%C3%89tat_%28Luxembourg%29) |
| Sources | [Luxembourg City Tourist Office](https://www.luxembourg-city.com/en/place/monument/hotel-de-bourgogne) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Minist%C3%A8re_d%27%C3%89tat_%28Luxembourg%29) |
| Pin | Hôtel de Bourgogne · 2 |
| Interior | none |

<a id="central-post-office"></a>
### Central Post Office

| | |
|---|---|
| Local name | Hôtel des Postes / Postgebai |
| Coordinates | 49.61104, 6.12747 |
| Category | landmark |
| Quarter | Ville Haute |
| About | The city's grand post office was raised between 1908 and 1910 to plans by state architect Sosthène Weis, who replaced his predecessor's Art Nouveau steel-and-glass scheme with a Neo-Renaissance design echoing the Grand Ducal Palace. Its sandstone façades, quarried at Ernzen, Dillingen and Bour, carry sculpture by Pierre Federspiel, Jean Mich, Claus Cito and Jean-Baptiste Wercollier. The building faces Place Hamilius and served as the main post office from 1910 until 2017, when the post moved to a new head office by the station. |
| Facts | Built: 1908-1910<br>Architect: Sosthène Weis<br>Style: Neo-Renaissance<br>Materials: sandstone façades<br>Use: main post office, 1910-2017 |
| Images | [`central-post-office__photo.jpg`](images/central-post-office__photo.jpg): Central Post Office |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Postgebai_Stad_L%C3%ABtzebuerg) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Postgebai_Stad_L%C3%ABtzebuerg) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/H%C3%B4tel_des_Postes_de_Luxembourg) |
| Pin | Central Post Office · 2 |

<a id="fort-lambert"></a>
### Lambert Redoubt

| | |
|---|---|
| Local name | Réduit Lambert / Fort Lambert |
| Coordinates | 49.61000, 6.12346 |
| Category | fortification |
| Quarter | Ville Haute |
| About | The Lambert Redoubt was the core of Fort Lambert, built in 1685 on the open plateau west of the old town when the French engineer Vauban strengthened the fortress. It was given a roof in 1835-36, but the whole fort was razed when the fortress was dismantled between 1868 and 1874. Its stone remains lay forgotten until digging for the Monterey underground car park uncovered them, and they were kept as a sunken ruin at the edge of the Municipal Park. |
| Facts | Built: 1685<br>Engineer: Vauban (attributed)<br>Demolished: 1868-1874<br>Rediscovered: during building of the Monterey car park (1990s)<br>Setting: Municipal Park, Avenue Monterey |
| Visiting | Visible from above on Avenue Monterey and from the Municipal Park. |
| Images | [`fort-lambert__photo.jpg`](images/fort-lambert__photo.jpg): Lambert Redoubt |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Lambert_Redoubt) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Lambert_Redoubt) · [Luxembourg City Tourist Office](https://www.luxembourg-city.com/fr/adresse/fortification/reduit-lambert) |
| Pin | Lambert Redoubt · 3 |
| Model | no |

<a id="cite-judiciaire"></a>
### Cité judiciaire

| | |
|---|---|
| Local name | Cité judiciaire / Geriichtsgebaier |
| Coordinates | 49.60781, 6.13423 |
| Category | government |
| Quarter | Ville Haute |
| About | Luxembourg's law courts were brought together on the Plateau du Saint-Esprit, a rocky spur above the Pétrusse and Alzette valleys that once held a convent of Poor Clares and later a citadel and barracks. Planned from the early 1990s to designs by Rob Krier, the complex had its first stone laid in October 2003 and opened in October 2008. Its cluster of pale blocks with steep slate roofs, set around squares and lanes, was meant to blend with the historic townscape. |
| Facts | Opened: 6 October 2008<br>First stone: 7 October 2003<br>Architect: Rob Krier (with Léon Krier)<br>Size: about 43,000 m², 16 courtrooms<br>Use: national courts and legal offices |
| Visiting | Open courtyards can be crossed on foot; buildings for court business only. |
| Images | [`cite-judiciaire__photo.jpg`](images/cite-judiciaire__photo.jpg): Cité judiciaire |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Judiciary_City) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Judiciary_City) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Helleg-Geescht-Plateau) · [Luxembourg City Tourist Office](https://www.luxembourg-city.com/en/place/monument/justice-quarter) |
| Pin | Cité judiciaire · 2 |

<a id="dicks-lentz-monument"></a>
### Dicks-Lentz Monument

| | |
|---|---|
| Local name | Monument Dicks-Lentz / Dicks-Lentz-Monument |
| Coordinates | 49.61129, 6.12860 |
| Category | landmark |
| Quarter | Ville Haute |
| About | Unveiled on 11 October 1903, this monument honours two founders of Luxembourgish-language writing: Edmond de la Fontaine, known as Dicks, and Michel Lentz, author of the patriotic song 'De Feierwon'. Georges Traus drew up the design and Pierre Federspiel made the sculptures. A column on a round, stepped base is crowned by a bronze lion holding the Luxembourg arms, flanked by a singing blacksmith and a woman arranging flowers. It stands in Square Jan Palach beside Place d'Armes. |
| Facts | Inaugurated: 11 October 1903<br>Design: Georges Traus<br>Sculptor: Pierre Federspiel<br>Honours: poets Dicks and Michel Lentz<br>Setting: Square Jan Palach, by Place d'Armes |
| Visiting | Public square, open at all times. |
| Images | [`dicks-lentz-monument__photo.jpg`](images/dicks-lentz-monument__photo.jpg): Dicks-Lentz Monument |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Dicks-Lentz-Monument) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Dicks-Lentz-Monument) |
| Pin | Dicks-Lentz Monument · 3 |
| Model | no |

<a id="bains-du-centre"></a>
### Badanstalt City Baths

| | |
|---|---|
| Local name | Badanstalt / Bains du Centre |
| Coordinates | 49.61373, 6.12880 |
| Category | sport |
| Quarter | Ville Haute |
| About | The Badanstalt is the city's historic bathhouse on Rue des Bains, built between 1873 and 1875 by the architect Pierre Funck together with his father-in-law Jean-François Eydt. Once a place where townspeople came to wash, it now runs as a small relaxation pool. Inside are a medium-sized indoor pool with whirlpools and water jets, saunas, a Turkish bath and a fitness room. |
| Facts | Built: 1873-1875<br>Architects: Pierre Funck and Jean-François Eydt<br>Use: public indoor pool and wellness centre<br>Address: Rue des Bains |
| Visiting | Public pool run by the city; open most days. |
| Images | [`bains-du-centre__photo.jpg`](images/bains-du-centre__photo.jpg): Badanstalt City Baths |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Badanstalt) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Badanstalt) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Badanstalt_%28Stad_L%C3%ABtzebuerg%29) |
| Pin | Badanstalt · 3 |

<a id="hotel-saint-maximin"></a>
### Refuge Saint-Maximin

| | |
|---|---|
| Local name | Refuge Saint-Maximin / Hôtel Saint-Maximin |
| Coordinates | 49.60996, 6.13198 |
| Category | government |
| Quarter | Ville Haute |
| About | This was the town house of the Benedictine abbey of Saint Maximin in Trier, the monastery from which Count Siegfried acquired the rock of Luxembourg in 963. Abbot Wilibrord Scheffer had the present three-storey Baroque building put up in 1751 on the corner of Rue Notre-Dame and Place Clairefontaine, beside the cathedral. After secularisation it passed through private hands, the German Confederation and, from 1867, the Luxembourg government. The Foreign Ministry left in 2017, and since 2019 it has housed the Prime Minister and the Ministry of State. |
| Facts | Built: 1751<br>Style: Baroque<br>Commissioned by: Abbot Wilibrord Scheffer of Saint Maximin, Trier<br>Address: 5 Rue Notre-Dame<br>Use: Ministry of State and office of the Prime Minister (since 2019)<br>Former use: Ministry of Foreign and European Affairs (until 2017) |
| Visiting | Government offices; seen from outside only. |
| Images | [`hotel-saint-maximin__photo.jpg`](images/hotel-saint-maximin__photo.jpg): Refuge Saint-Maximin |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Refuge_Saint-Maximin) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Refuge_Saint-Maximin) · [Wikipedia (de)](https://de.wikipedia.org/wiki/Refugium_St._Maximin) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Refuge_Sankt_Maximin) |
| Pin | Ministry of State · 3 |

<a id="central-bank"></a>
### Central Bank of Luxembourg

| | |
|---|---|
| Local name | Banque centrale du Luxembourg / Zentralbank vu Lëtzebuerg |
| Coordinates | 49.61475, 6.12958 |
| Category | government |
| Quarter | Ville Haute |
| About | Luxembourg's central bank was set up in 1998 as the country's member of the Eurosystem, taking over from the Institut Monétaire Luxembourgeois. Its seat at 2 Boulevard Royal, on the corner of the Côte d'Eich, was the head office of the Banque Internationale: a Neoclassical stone bank of 1901–1902 by Pierre and Paul Funck, joined to a 1962 office block. The central bank raised the 1962 wing, gave it a new façade and named it the Pierre Werner Building after the 'father of the euro'. |
| Facts | Founded: 1998<br>Main building: 1901–1902, architects Pierre and Paul Funck<br>Style: Neoclassical<br>Annex: 1962 office block, now the Pierre Werner Building<br>Address: 2 Boulevard Royal<br>Use: national central bank in the Eurosystem |
| Visiting | Working offices; seen from outside only. |
| Images | [`central-bank__photo.jpg`](images/central-bank__photo.jpg): Central Bank of Luxembourg |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Central_Bank_of_Luxembourg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Central_Bank_of_Luxembourg) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Banque_centrale_du_Luxembourg) · [BCL: history of the head office (René Link)](https://www.bcl.lu/fr/publications/autres_publications/BCL_HISTORIQUE_SIEGE.pdf) |
| Pin | Central Bank · 2 |

<a id="solidarity-monument"></a>
### National Monument of Luxembourg Solidarity

| | |
|---|---|
| Local name | Monument national de la Solidarité luxembourgeoise / Nationalmonument vun der Lëtzebuerger Solidaritéit |
| Coordinates | 49.60704, 6.13408 |
| Category | landmark |
| Quarter | Ville Haute |
| About | Standing on the Kanounenhiwwel above the Pétrusse valley, this memorial honours the dead of the Second World War, the resistance and the nation's solidarity against the Nazi occupation. Prime Minister Pierre Werner launched the project in 1968; a jury chose the design by artist François Gillen and architect René Mailliet. Built in a few months, it was inaugurated on 10 October 1971, anniversary of the 1941 census that the population had defied. An eternal flame burns before it, and a crypt holds an unhewn stone for the victims. |
| Facts | Built: May–October 1971<br>Inaugurated: 10 October 1971<br>Architect: René Mailliet<br>Artist: François Gillen<br>Features: eternal flame, paved inner court and crypt<br>Use: national war memorial |
| Visiting | Outside only; the flame and forecourt can be seen at any time. |
| Images | [`solidarity-monument__photo.jpg`](images/solidarity-monument__photo.jpg): National Monument of Luxembourg Solidarity |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Nationalmonument_vun_der_L%C3%ABtzebuerger_Solidarit%C3%A9it) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Nationalmonument_vun_der_L%C3%ABtzebuerger_Solidarit%C3%A9it) |
| Pin | Solidarity Monument · 2 |
| Model | no |

<a id="saint-alphonse"></a>
### Saint-Alphonse Church

| | |
|---|---|
| Local name | Église Saint-Alphonse / Paterekierch |
| Coordinates | 49.61318, 6.13026 |
| Category | church |
| Quarter | Ville Haute |
| About | Known locally as the Paterekierch, this is the church of the Redemptorist Fathers, dedicated to their founder Alphonsus Liguori and standing on the corner of Rue des Capucins and Rue Beaumont beside their monastery. Antoine Hartmann designed it in the Neo-Romanesque style; work began in 1856 and it was consecrated in 1858. Because it stood right by the fortress wall its two towers had to be kept low, while the nave rises unusually high to catch light in the crowded old town. |
| Facts | Built: 1856–1858<br>Architect: Antoine Hartmann<br>Style: Neo-Romanesque<br>Use: Redemptorist church<br>Heritage status: national monument (2018) |
| Visiting | Open to the public during services. |
| Images | [`saint-alphonse__photo.jpg`](images/saint-alphonse__photo.jpg): Saint-Alphonse Church |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_Saint-Alphonse_vu_L%C3%ABtzebuerg) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_Saint-Alphonse_vu_L%C3%ABtzebuerg) |
| Pin | Saint-Alphonse · 3 |

<a id="hammelsmarsch-fountain"></a>
### Hämmelsmarsch Fountain

| | |
|---|---|
| Local name | Hämmelsmarsch-Buer / Fontaine Hämmelsmarsch |
| Coordinates | 49.61186, 6.13117 |
| Category | landmark |
| Quarter | Ville Haute |
| About | This bronze fountain on the Roude Pëtz celebrates the Hämmelsmarsch, the procession of musicians and sheep that goes round town at the parish fair. Sculptor Wil Lofy made it in 1981–1982, putting himself in the group as the accordion player; four musicians, five sheep and two children stand on a six-sided plinth, with water flowing from the instruments into a hexagonal basin. It was unveiled in August 1982 at the opening of the Schueberfouer, and was restored in France in 2023–2024. |
| Facts | Sculptor: Wil Lofy<br>Made: 1981–1982<br>Unveiled: August 1982<br>Material: bronze on a stone plinth<br>Restored: 2023–2024 |
| Visiting | In a pedestrian square; open at all times. |
| Images | [`hammelsmarsch-fountain__photo.jpg`](images/hammelsmarsch-fountain__photo.jpg): Hämmelsmarsch Fountain |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/H%C3%A4mmelsmarsch-Brunnen) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/H%C3%A4mmelsmarsch-Brunnen) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/H%C3%A4mmelsmarsch-Buer) |
| Pin | Hämmelsmarsch · 3 |
| Model | no |

<a id="maison-de-raville"></a>
### Maison de Raville

| | |
|---|---|
| Local name | Maison de Raville |
| Coordinates | 49.61071, 6.13221 |
| Category | landmark |
| Quarter | Ville Haute |
| About | Jacques de Raville, of a noble Luxembourg family, built this Renaissance-era town house at 4 Rue de la Reine around 1575. Over the centuries it belonged to the lords of Ierwerleng, Orval Abbey and a string of wealthy families before banks bought it in 1975 and 1998 and renovated it in depth. The state later bought it along with the neighbouring Maison Wiltheim, and since 2012 the complex has housed the Luxembourg regulator ILR as well as parliamentary and government offices. |
| Facts | Built: around 1575<br>Built for: Jacques de Raville<br>Address: 4 Rue de la Reine<br>Use: offices of the Institut luxembourgeois de régulation (since 2012)<br>Heritage status: supplementary inventory (1975) |
| Visiting | Offices; seen from outside only. |
| Images | [`maison-de-raville__photo.jpg`](images/maison-de-raville__photo.jpg): Maison de Raville |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Maison_de_Raville) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Maison_de_Raville) |
| Pin | Maison de Raville · 3 |

<a id="castle-bridge"></a>
### Castle Bridge

| | |
|---|---|
| Local name | Pont du Château / Schlassbréck |
| Coordinates | 49.61160, 6.13593 |
| Category | bridge |
| Quarter | Bock |
| About | The Castle Bridge links the Fish Market in the old town with the Bock promontory, where Luxembourg's first castle stood in the 10th century. The original was built in 1735 by the Kintzelé brothers, master builders from Bridel, and was widened in 1933. In 1993 it was demolished and rebuilt to the old design but wider, using red local sandstone: one tall arch carries the road over the Corniche, with a row of five smaller arches above it and a casemate tunnel running between the two levels. |
| Facts | Original built: 1735, by the Kintzelé brothers<br>Rebuilt: 1993, as a widened replica<br>Material: red Luxembourg sandstone<br>Width: 8.6 m<br>Carries: national road N1 over Rue Sosthène-Weis |
| Visiting | Public road bridge, open at all times; best seen from the Corniche below. |
| Images | [`castle-bridge__photo.jpg`](images/castle-bridge__photo.jpg): Castle Bridge |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Schlossbr%C3%BCcke_%28Luxemburg%29) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Schlossbr%C3%BCcke_%28Luxemburg%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Schlassbr%C3%A9ck_%28Stad_L%C3%ABtzebuerg%29) |
| Pin | Castle Bridge · 2 |
| Model | no |

<a id="dent-creuse"></a>
### Hollow Tooth

| | |
|---|---|
| Local name | Dent creuse / Huelen Zant |
| Coordinates | 49.61202, 6.13767 |
| Category | fortification |
| Quarter | Bock |
| About | The jagged stump of masonry on the Bock rock is often taken for a relic of Count Siegfried's castle, but it is in fact the left-hand tower of the fortress's second gate. When the citadel on the Bock was dismantled in 1874, state architect Charles Arendt had this tower deliberately reshaped as a mock ruin and left standing, as the romantic taste of the day liked. |
| Facts | Origin: tower of the second gate of the Bock fortifications<br>Made a ruin: 1874, by Charles Arendt<br>Type: deliberate mock ruin<br>Setting: Bock promontory above the Alzette |
| Visiting | Seen from the Montée de Clausen and the Bock area; open-air site. |
| Images | [`dent-creuse__photo.jpg`](images/dent-creuse__photo.jpg): Hollow Tooth |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Huelen_Zant) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Huelen_Zant) |
| Pin | Hollow Tooth · 2 |
| Model | no |

<a id="rham-plateau"></a>
### Rham Plateau

| | |
|---|---|
| Local name | Plateau du Rham / Rumm |
| Coordinates | 49.60941, 6.13847 |
| Category | fortification |
| Quarter | Grund |
| About | The Rham Plateau is a height ringed on three sides by a loop of the Alzette, settled early and drawn into the fortress when the Wenceslas Wall was built around the turn of the 15th century. Its old name, Dinsel, probably comes from the Latin for island. In the late 17th century Vauban had five long military barracks built here; since the late 19th century they have housed social institutions, and today an old people's home. The front of the plateau looks across to the Saint-Esprit citadel and the Corniche. |
| Facts | Fortified: from the late 14th / 15th century<br>Barracks: five, built under Vauban, late 17th century<br>Use: retirement home<br>Setting: in a loop of the Alzette above Grund |
| Visiting | Outside only; views from the surrounding streets and the Corniche opposite. |
| Images | [`rham-plateau__photo.jpg`](images/rham-plateau__photo.jpg): Rham Plateau |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Rham-Plateau) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Rham-Plateau) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Rumm-Befestegungen) |
| Pin | Rham Plateau · 2 |

<a id="saint-quirin"></a>
### Saint-Quirin Chapel

| | |
|---|---|
| Local name | Chapelle Saint-Quirin / Gräinskapell |
| Coordinates | 49.60567, 6.13510 |
| Category | church |
| Quarter | Pétrusse valley |
| About | Tucked against the rock face of the Pétrusse valley, this small chapel grew up beside a spring long believed to heal, and the site is thought to have been a place of worship since late Roman times. It was dedicated to the martyr Quirinus of Neuss in the 11th century. Part of the chapel is cut into the cliff itself, fronted by a Gothic façade of 1355, while the roof and little bell turret were added in the 19th century. |
| Facts | Façade: 1355, Gothic<br>Dedicated: 11th century, to Quirinus of Neuss<br>Roof and bell turret: 19th century<br>Setting: partly carved into the rock beside a spring |
| Visiting | The outside can be seen from the footpaths of the Pétrusse valley. |
| Images | [`saint-quirin__photo.jpg`](images/saint-quirin__photo.jpg): Saint-Quirin Chapel<br>[`saint-quirin__photo-2.jpg`](images/saint-quirin__photo-2.jpg): Saint-Quirin Chapel in the Pétrusse valley, seen from above |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Chapelle_Saint-Quirin_%28Luxembourg%29) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Chapelle_Saint-Quirin_%28Luxembourg%29) · [Wikipedia (de)](https://de.wikipedia.org/wiki/Quirinuskapelle_%28Luxemburg%29) |
| Pin | Saint-Quirin Chapel · 1 |

<a id="place-de-paris"></a>
### Place de Paris

| | |
|---|---|
| Local name | Place de Paris / Paräisser Plaz |
| Coordinates | 49.60343, 6.13069 |
| Category | square |
| Quarter | Gare |
| About | Place de Paris was laid out by the state after the Adolphe Bridge was built, on ground once taken up by the fortress, and got its name in 1907 from the Hôtel de Paris that went up beside it in 1909-1912. Until 1920 it marked the boundary with the commune of Hollerich, where a small toll pavilion collected duty on goods entering the city. Avenue de la Liberté runs through it, and when the tram reached the station the square was remade as an open plaza with 18 new plane trees, reopening in 2021. |
| Facts | Named: 5 December 1907<br>Former name: Place de l'Éventail<br>Redesigned: opened 26 June 2021<br>Landmark building: Hôtel de Paris (1909-1912)<br>Use: public square and tram stop |
| Visiting | Public square, open at all times; served by the tram. |
| Images | [`place-de-paris__photo.jpg`](images/place-de-paris__photo.jpg): Place de Paris and Avenue de la Liberté on an early 20th-century postcard |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Place_de_Paris_%28Luxembourg%29) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Place_de_Paris_%28Luxembourg%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Place_de_Paris_%28Stad_L%C3%ABtzebuerg%29) |
| Pin | Place de Paris · 3 |
| Model | no |

<a id="villa-pauly"></a>
### Villa Pauly

| | |
|---|---|
| Local name | Villa Pauly |
| Coordinates | 49.60609, 6.12502 |
| Category | landmark |
| Quarter | Gare |
| About | Villa Pauly on Boulevard de la Pétrusse was built in 1923 for the surgeon Norbert Pauly to designs by Mathias Martin, in an eclectic style whose corner towers recall late medieval and Renaissance castles. From 1940 to 1944 it was the Gestapo's headquarters in Luxembourg, and thousands of people were questioned here, many tortured in its cellars. Since 2001 it has housed the documentation and research centre on the Resistance, and it was listed as a national monument in 1989. |
| Facts | Built: 1923<br>Architect: Mathias Martin<br>Style: eclectic, castle-like corner towers<br>Wartime use: Gestapo headquarters, 1940-1944<br>Use: Resistance documentation and research centre<br>Heritage status: national monument (1989) |
| Images | [`villa-pauly__photo.jpg`](images/villa-pauly__photo.jpg): Villa Pauly |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Villa_Pauly) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Villa_Pauly) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Villa_Pauly) |
| Pin | Villa Pauly · 2 |

<a id="arbed-building"></a>
### ARBED Building

| | |
|---|---|
| Local name | Bâtiment ARBED / Arbedsgebai (19 Liberté) |
| Coordinates | 49.60565, 6.12982 |
| Category | landmark |
| Quarter | Gare |
| About | The former head office of the ARBED steel company, later ArcelorMittal, faces the rose garden on Avenue de la Liberté. Designed by the French architect René Théry and completed around 1922, it borrows from 17th- and 18th-century French châteaux: a steel and concrete frame behind sandstone façades, with a sculpture by René Rozet of Victory crowning Mercury over the entrance. Since 2014 it has belonged to Spuerkeess, which reopened it in 2016 as '19 Liberté'. |
| Facts | Completed: c. 1922<br>Architect: René Théry (works led by Sosthène Weis)<br>Style: inspired by French châteaux<br>Materials: steel and reinforced concrete, sandstone façade<br>Use: offices and event rooms of Spuerkeess ('19 Liberté', since 2016) |
| Visiting | Outside only. |
| Images | [`arbed-building__photo.jpg`](images/arbed-building__photo.jpg): ARBED Building |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/ARBED_building) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/ARBED_building) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Arbedsgebai) |
| Pin | ARBED Building · 1 |

<a id="publications-office"></a>
### Publications Office of the European Union

| | |
|---|---|
| Local name | Office des publications de l'Union européenne |
| Coordinates | 49.59971, 6.13046 |
| Category | eu-institution |
| Quarter | Gare |
| About | Set up in 1969, the Publications Office is the EU's official publisher, issuing the Official Journal daily in all the Union's languages and running services such as EUR-Lex and the EU's open data portal. Its headquarters is now the Mercier-POST building near the station, the former offices of the Luxembourg post, refitted for the European Commission and inaugurated in March 2024. The building offers about 15,000 m² of open, shared workspace, which it also shares with part of DG CONNECT. |
| Facts | Founded: 16 January 1969<br>Building: Mercier-POST, inaugurated 2024<br>Former use: offices of POST Luxembourg<br>Size: about 15,000 m², 670 workstations<br>Use: EU publishing, Official Journal, EUR-Lex |
| Visiting | Office building; not open to visitors. |
| Images | [`publications-office__photo.jpg`](images/publications-office__photo.jpg): Publications Office of the European Union |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Publications_Office_of_the_European_Union) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Publications_Office_of_the_European_Union) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Office_des_publications_de_l%27Union_europ%C3%A9enne) · [Official site](https://op.europa.eu/) · [Chronicle.lu](https://chronicle.lu/category/at-home/49091-commissioner-hahn-hrh-grand-duke-henri-inaugurate-new-commission-building-in-luxembourg) |
| Pin | EU Publications Office · 3 |

<a id="sacre-coeur"></a>
### Sacred Heart Church

| | |
|---|---|
| Local name | Église du Sacré-Cœur / Garer Kierch |
| Coordinates | 49.60445, 6.13141 |
| Category | church |
| Quarter | Gare |
| About | The parish church of the station quarter stands on the Plateau Bourbon, where Rue Dicks meets the Boulevard de la Pétrusse. It was designed by city architect Nicolas Petit, with the future bishop Léon Lommel involved in its planning; the foundation stone was laid in 1930, it was blessed in 1932 and solemnly consecrated in 1936. The interior is largely the work of the German artist Otto Linnemann, whose frescoes were restored in 2008–2010. |
| Facts | Built: 1930–1932<br>Consecrated: 30 April 1936<br>Architect: Nicolas Petit<br>Interior and frescoes: Otto Linnemann<br>Use: parish church of the Gare quarter |
| Visiting | Open to the public during services. |
| Images | [`sacre-coeur__photo.jpg`](images/sacre-coeur__photo.jpg): Sacred Heart Church |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Gare) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Gare) |
| Pin | Sacred Heart Church · 2 |

<a id="rotondes"></a>
### Rotondes

| | |
|---|---|
| Local name | Rotondes / Rotonden |
| Coordinates | 49.60140, 6.13647 |
| Category | culture |
| Quarter | Bonnevoie |
| About | Two round railway engine sheds, each 52 metres across and 15 metres high, built in 1877 beside the tracks in Bonnevoie to house and service steam locomotives, 18 to a shed. They lost their railway role after 1907 and later served as a warehouse and a bus garage. Listed as national monuments in 1991, they were used for the 2007 Capital of Culture year and, after renovation from 2013, became a cultural centre with a theatre, exhibitions, concerts and a bistro. |
| Facts | Built: 1877<br>Size: 52 m diameter, 15 m high each<br>Original use: steam locomotive roundhouses (18 engines each)<br>Heritage status: national monument (1991)<br>Use: cultural centre |
| Visiting | Open for performances, concerts and events; bistro open to the public. |
| Images | [`rotondes__photo.jpg`](images/rotondes__photo.jpg): Rotondes<br>[`rotondes__photo-2.jpg`](images/rotondes__photo-2.jpg): Rotunda 1 seen from the street |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Rotondes_%28Luxembourg%29) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Rotondes_%28Luxembourg%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Rotonden) · [Official site](http://rotondes.lu/) |
| Pin | Rotondes · 1 |

<a id="banannefabrik"></a>
### Banannefabrik

| | |
|---|---|
| Local name | Banannefabrik / Centre de production et de création artistique |
| Coordinates | 49.59818, 6.13571 |
| Category | culture |
| Quarter | Bonnevoie |
| About | This arts centre in Rue du Puits takes its nickname, the 'banana factory', from its past as a fruit warehouse. The fruit and vegetable wholesaler Coprilux had it built in 1960 to plans by Robert-F. Heintz-Sturm, and it later served La Provençale until 1979. After years of decline, a group from the cultural scene saw its potential in the early 1990s, and it was turned into a centre for artistic production, now run by the Banannefabrik non-profit association. |
| Facts | Built: 1960<br>Architect: Robert-F. Heintz-Sturm<br>Former use: fruit and vegetable warehouse<br>Use: artistic production and creation centre (CPCA)<br>Address: Rue du Puits, Bonnevoie |
| Visiting | Open to the public for performances and events. |
| Images | [`banannefabrik__photo.jpg`](images/banannefabrik__photo.jpg): Banannefabrik |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Banannefabrik) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Banannefabrik) · [Official site](https://www.banannefabrik.lu/) |
| Pin | Banannefabrik · 3 |

<a id="den-atelier"></a>
### Den Atelier

| | |
|---|---|
| Local name | Den Atelier |
| Coordinates | 49.59877, 6.12615 |
| Category | culture |
| Quarter | Hollerich |
| About | Den Atelier is Luxembourg's best-known club venue for rock, indie and pop concerts, holding about 1,200 people. Its name means 'the workshop' in Luxembourgish, because it occupies a former Renault lorry garage on Rue de Hollerich. Its founders wanted a stage like Brussels's Ancienne Belgique or Amsterdam's Paradiso, and since opening in October 1995 it has hosted acts from Muse and Placebo to Kraftwerk and Arctic Monkeys. |
| Facts | Opened: 23 October 1995<br>Capacity: about 1,200<br>Former use: Renault lorry garage<br>Use: concert venue<br>Address: Rue de Hollerich |
| Visiting | Open for concerts; see the venue's programme. |
| Images | [`den-atelier__photo.jpg`](images/den-atelier__photo.jpg): A concert inside Den Atelier |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Den_Atelier) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Den_Atelier) |
| Pin | Den Atelier · 3 |

<a id="stade-hammerel"></a>
### Stade Achille Hammerel

| | |
|---|---|
| Local name | Stade Achille-Hammerel |
| Coordinates | 49.60460, 6.14063 |
| Category | sport |
| Quarter | Verlorenkost |
| About | This football ground in the Verlorenkost area of Bonnevoie is the home of Racing FC Union Luxembourg and, until 2005, was the home of Union Luxembourg. It holds just under 6,000 spectators. Beyond football it has a place in local music history: on 6 June 1971 Deep Purple headlined Luxembourg's first rock festival here, in front of about 4,000 people. |
| Facts | Capacity: 5,814<br>Home club: Racing FC Union Luxembourg<br>Use: football stadium<br>Notable event: Deep Purple concert, 6 June 1971 |
| Visiting | Open for matches and events. |
| Images | [`stade-hammerel__photo.jpg`](images/stade-hammerel__photo.jpg): Stade Achille Hammerel |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Stade_Achille_Hammerel) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Stade_Achille_Hammerel) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Stade_Achille-Hammerel) |
| Pin | Stade Hammerel · 3 |

<a id="grand-theatre"></a>
### Grand Théâtre de Luxembourg

| | |
|---|---|
| Local name | Grand Théâtre de la Ville de Luxembourg |
| Coordinates | 49.61778, 6.12787 |
| Category | culture |
| Quarter | Limpertsberg |
| About | The Grand Théâtre is the city's main stage for drama, opera and dance. It was planned to replace the cramped Théâtre des Capucins: the Parisian architect Alain Bourbonnais won a 1958 competition, work began in 1959 and the building opened as the Municipal Theatre on 15 April 1964. Its long, low modernist front faces the Rond-Point Schuman, and a 2002-2003 refit by the Berlin firm Gerling + Arendt modernised the stage machinery, acoustics and lighting. |
| Facts | Opened: 15 April 1964<br>Architect: Alain Bourbonnais<br>Built: 1959-1964<br>Renovated: 2002-2003, Gerling + Arendt<br>Use: theatre, opera and dance venue |
| Visiting | Open for performances; see the Théâtres de la Ville de Luxembourg programme. |
| Images | [`grand-theatre__photo.jpg`](images/grand-theatre__photo.jpg): Grand Théâtre de Luxembourg<br>[`grand-theatre__photo-2.jpg`](images/grand-theatre__photo-2.jpg): Grand Théâtre de Luxembourg, another view |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Grand_Th%C3%A9%C3%A2tre_de_Luxembourg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Grand_Th%C3%A9%C3%A2tre_de_Luxembourg) · [Official site](http://www.theatres.lu) |
| Pin | Grand Théâtre · 1 |

<a id="lycee-robert-schuman"></a>
### Lycée Robert-Schuman

| | |
|---|---|
| Local name | Lycée Robert-Schuman |
| Coordinates | 49.61900, 6.12697 |
| Category | education |
| Quarter | Limpertsberg |
| About | This state secondary school began in 1909 as a private girls' lycée set up by an association founded by Aline Mayrisch-de Saint-Hubert, and became a public school in 1911. Its own building by the Glacis, designed by Nicolas Petit, opened in 1926 and still forms the old core. Co-education arrived in 1972, when the school took the name of Robert Schuman, and it was enlarged by Laurent Schmit (completed 1987) and again by Françoise Folmer between 1999 and 2007. |
| Facts | Founded: 1909 (public school from 1911)<br>Original building: 1926, Nicolas Petit<br>Extensions: 1979-1987 (Laurent Schmit), 1999-2007 (Françoise Folmer)<br>Renamed: 1972<br>Use: public secondary school |
| Visiting | School premises, not open to visitors. |
| Images | [`lycee-robert-schuman__photo.jpg`](images/lycee-robert-schuman__photo.jpg): Lycée Robert-Schuman |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Lyc%C3%A9e_Robert-Schuman) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Lyc%C3%A9e_Robert-Schuman) · [Official site](http://www.lrsl.lu/) |
| Pin | Lycée Robert-Schuman · 2 |

<a id="cine-utopia"></a>
### Ciné Utopia

| | |
|---|---|
| Local name | Kino Utopia |
| Coordinates | 49.61730, 6.12140 |
| Category | culture |
| Quarter | Limpertsberg |
| About | Members of the Ciné-Club 80 opened Utopia on 15 December 1983 in a former garage on Avenue de la Faïencerie, with a single screen of 145 seats. It proved so popular that a second room followed in 1985, and by 1989 it had grown to five screens. Long known for arthouse and international films, the cinema has belonged to the Kinepolis group since 2015. |
| Facts | Opened: 15 December 1983<br>Founded by: members of Ciné-Club 80<br>Building: converted former garage<br>Screens: five (since 1989)<br>Owner: Kinepolis group (since 2015) |
| Visiting | Cinema open for screenings. |
| Images | [`cine-utopia__photo.jpg`](images/cine-utopia__photo.jpg): Ciné Utopia |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Utopia_%28Kino%29) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Utopia_%28Kino%29) |
| Pin | Ciné Utopia · 3 |

<a id="french-mausoleum"></a>
### Mausoleum of the French Soldiers

| | |
|---|---|
| Local name | Mausolée des soldats français |
| Coordinates | 49.61620, 6.11819 |
| Category | landmark |
| Quarter | Limpertsberg |
| About | This war memorial in the Notre-Dame Cemetery honours French soldiers who died in Luxembourg during the First World War, along with unknown Luxembourgers of the Foreign Legion who fell in the Battle of the Marne. It was designed by the architects Léon Muller and Joseph Nouveau, with sculpture by Ernest Grosber and bronze ornament by Michel Haagen, and was inaugurated on 16 November 1924. It is built of Bohemian granite and sandstone from the Ernzen quarries. |
| Facts | Inaugurated: 16 November 1924<br>Architects: Léon Muller and Joseph Nouveau<br>Sculptor: Ernest Grosber<br>Materials: granite and Ernzen sandstone<br>Setting: Notre-Dame Cemetery |
| Visiting | Inside the cemetery, open during cemetery hours. |
| Images | [`french-mausoleum__photo.jpg`](images/french-mausoleum__photo.jpg): Mausoleum of the French Soldiers |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Mausoleum_vun_de_frans%C3%A9ischen_Zaldoten_zu_L%C3%ABtzebuerg) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Mausoleum_vun_de_frans%C3%A9ischen_Zaldoten_zu_L%C3%ABtzebuerg) |
| Pin | French Mausoleum · 3 |
| Model | no |

<a id="schuman-monument"></a>
### Robert Schuman Monument

| | |
|---|---|
| Local name | Monument Robert Schuman / Robert-Schuman-Monument |
| Coordinates | 49.61717, 6.12907 |
| Category | landmark |
| Quarter | Limpertsberg |
| About | Standing on Boulevard Robert Schuman at the city end of the Red Bridge, this memorial honours the French statesman whose declaration of 9 May 1950 launched European integration. Designed by architect Robert Lentz, it was unveiled together with the bridge on 24 October 1966. Three tall steel girders rise from a concrete base carved with quotations from the declaration, their tops cut into six points for the six founding members of the Community. |
| Facts | Unveiled: 24 October 1966<br>Architect: Robert Lentz<br>Materials: concrete base, three steel girders<br>Symbolism: six points for the six founding states |
| Visiting | Open-air monument, accessible at all times. |
| Images | [`schuman-monument__photo.jpg`](images/schuman-monument__photo.jpg): Robert Schuman Monument |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Robert-Schuman-Monument) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Robert-Schuman-Monument) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Robert-Schuman_Monument) |
| Pin | Schuman Monument · 2 |
| Model | no |

<a id="lycee-arts-et-metiers"></a>
### Lycée des Arts et Métiers

| | |
|---|---|
| Local name | Lycée des Arts et Métiers / Handwierkerschoul |
| Coordinates | 49.62202, 6.12576 |
| Category | education |
| Quarter | Limpertsberg |
| About | Created by law in 1896 at the urging of Paul Eyschen to give young craftsmen a broader education, the former crafts school is the country's oldest technical secondary school. In 1910 it took over the Jesuits' Bellevue house in Limpertsberg, and state architect Sosthène Weis added workshops by 1911. Wings followed in 1948-53 and the school was enlarged again in 1968-71. It took its present name in 2015. |
| Facts | Founded: 14 March 1896<br>Architect: Sosthène Weis (workshops, 1909-1911)<br>Extensions: 1948-1953, 1968-1971<br>Heritage status: national monument<br>Use: technical and arts secondary school |
| Visiting | Outside only; a working school. |
| Images | [`lycee-arts-et-metiers__photo.jpg`](images/lycee-arts-et-metiers__photo.jpg): Lycée des Arts et Métiers |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Lyc%C3%A9e_des_Arts_et_M%C3%A9tiers) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Lyc%C3%A9e_des_Arts_et_M%C3%A9tiers) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Lyc%C3%A9e_des_arts_et_m%C3%A9tiers) · [Official site](https://www.ltam.lu/) |
| Pin | Arts et Métiers · 3 |

<a id="orthodox-church"></a>
### Russian Orthodox Church of Saints Peter and Paul

| | |
|---|---|
| Local name | Église des Saints-Apôtres-Pierre-et-Paul / Russesch-orthodox Kierch |
| Coordinates | 49.61422, 6.11952 |
| Category | church |
| Quarter | Limpertsberg |
| About | Luxembourg's first Russian Orthodox church serves a parish founded in 1928 by Russian émigrés, many of them former soldiers of General Kornilov's army who came to work in quarries and factories. After the city granted a plot on Rue Jean-Pierre Probst in 1975, Archbishop Anthony laid the first stone in 1979. The church was built largely by the parishioners themselves, led by the priest Sergey Puch, and consecrated in 1982. |
| Facts | Built: 1979-1982<br>Consecrated: 12 July 1982<br>Parish founded: 1928<br>Use: Russian Orthodox church (Russian Orthodox Church Outside Russia) |
| Visiting | Open to the public during services. |
| Images | [`orthodox-church__photo.jpg`](images/orthodox-church__photo.jpg): Russian Orthodox Church of Saints Peter and Paul |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/St._Peter_and_Paul_Church%2C_Luxembourg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/St._Peter_and_Paul_Church%2C_Luxembourg) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/%C3%89glise_des_Saints-Ap%C3%B4tres-Pierre-et-Paul_de_Luxembourg) |
| Pin | Orthodox Church · 2 |

<a id="glacis"></a>
### Glacis

| | |
|---|---|
| Local name | Champ du Glacis / Glacis |
| Coordinates | 49.61691, 6.12412 |
| Category | square |
| Quarter | Limpertsberg |
| About | The Glacis is the broad open ground between Limpertsberg and the old town, named after the cleared slope that lay in front of the fortress walls so that attackers had nowhere to hide. After the fortress was dismantled it became a public square, and today it is the city's largest open-air car park, with room for some 1,200 cars. Every late summer it fills with the rides and stalls of the Schueberfouer, the funfair founded in 1340 by John the Blind and held here since 1610. |
| Facts | Origin: fortress glacis (open firing ground)<br>Use: car park, about 1,200 spaces<br>Event: Schueberfouer funfair, held here since 1610<br>Fair founded: 1340 by John the Blind |
| Visiting | Open space at all times; the Schueberfouer runs from late August into September. |
| Images | [`glacis__photo.jpg`](images/glacis__photo.jpg): The Glacis in 1916, during a wartime potato distribution (historic photograph) |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Glacis_%28Lampertsbierg%29) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Glacis_%28Lampertsbierg%29) · [Wikipedia (en)](https://en.wikipedia.org/wiki/Schueberfouer) |
| Pin | Glacis · 1 |
| Model | no |

<a id="lycee-technique-centre"></a>
### Lycée technique du Centre

| | |
|---|---|
| Local name | Lycée technique du Centre (LTC) |
| Coordinates | 49.62463, 6.11652 |
| Category | education |
| Quarter | Limpertsberg |
| About | The Lycée technique du Centre is a public secondary school focused on technical trades. It grew out of vocational classes held after the Second World War in an annex of the Dominican convent on Limpertsberg; after the 1953 law on vocational training, the city's trade school replaced that annex with a new building. It took its present name in 1979 and now also has an annex on Kirchberg. |
| Facts | Founded: 1953 (vocational centre)<br>Present name: since 1979<br>Type: public technical secondary school<br>Sites: main building on Limpertsberg, annex on Kirchberg<br>UNESCO Associated School: since 2017 |
| Visiting | School; not open to visitors. |
| Images | [`lycee-technique-centre__photo.jpg`](images/lycee-technique-centre__photo.jpg): Lycée technique du Centre |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Lyc%C3%A9e_technique_du_Centre) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Lyc%C3%A9e_technique_du_Centre) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Lyc%C3%A9e_technique_du_Centre) |
| Pin | Lycée du Centre · 3 |

<a id="notre-dame-cemetery"></a>
### Notre-Dame Cemetery

| | |
|---|---|
| Local name | Cimetière Notre-Dame / Nikloskierfecht |
| Coordinates | 49.61638, 6.11840 |
| Category | park |
| Quarter | Limpertsberg |
| About | When the old St Nicholas church in the town centre was pulled down, its parish graveyard was moved in 1779 outside the walls to the Glacis, which is why locals still call it the Nikloskierfecht. It grew from a small burial ground by the Notre-Dame chapel, used since 1691 for people executed for non-criminal offences such as desertion. Today it is the largest of the city's fourteen cemeteries, a green, walled space of tree-lined paths and old family tombs. |
| Facts | Established: 1779-1780<br>Origin: parish graveyard of St Nicholas<br>Earlier burial ground: from 1691<br>Largest of the city's 14 cemeteries |
| Visiting | Open to the public during cemetery hours. |
| Images | [`notre-dame-cemetery__photo.jpg`](images/notre-dame-cemetery__photo.jpg): Notre-Dame Cemetery |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Notre-Dame_Cemetery_%28Luxembourg%29) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Notre-Dame_Cemetery_%28Luxembourg%29) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Cimeti%C3%A8re_Notre-Dame_de_Luxembourg) |
| Pin | Notre-Dame Cemetery · 2 |
| Model | no |

<a id="glacis-chapel"></a>
### Glacis Chapel

| | |
|---|---|
| Local name | Chapelle du Glacis / Glaciskapell |
| Coordinates | 49.61487, 6.12218 |
| Category | church |
| Quarter | Limpertsberg |
| About | The Glacis Chapel stands on the roundabout where Boulevard Joseph II meets Boulevard de la Foire, about 100 metres from the first Marian chapel built here in 1626 around a statue set up by the Jesuit Jacques Brocquart; that chapel was destroyed by French revolutionary troops in 1796. The present building was put up at the wish of Bishop Nicolas Adames to plans by state architect Charles Arendt and consecrated in 1885. Dedicated to the Nativity of the Virgin, it was listed as a national monument in 2020. |
| Facts | Consecrated: 1885<br>Architect: Charles Arendt<br>Dedication: Nativity of the Virgin Mary<br>Heritage status: national monument (2020)<br>First chapel nearby: 1626, destroyed 1796 |
| Visiting | Open to the public during services and church events. |
| Images | [`glacis-chapel__photo.jpg`](images/glacis-chapel__photo.jpg): Glacis Chapel |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Kapelle_Glacis_%28Luxemburg%29) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Kapelle_Glacis_%28Luxemburg%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Glaciskapell) |
| Pin | Glacis Chapel · 3 |

<a id="saint-joseph"></a>
### Saint-Joseph Church, Limpertsberg

| | |
|---|---|
| Local name | Église Saint-Joseph / Jousefskierch Lampertsbierg |
| Coordinates | 49.62065, 6.12102 |
| Category | church |
| Quarter | Limpertsberg |
| About | With Limpertsberg's population growing and the cathedral far away, the city council decided in 1909 to give the quarter its own church and rectory. City architect Nicolas Petit designed it, and the firm of Achille Giorgetti built it between 1910 and 1913; it was consecrated on 30 April 1913. It is one of the few Neo-Romanesque churches in a country where Neo-Gothic is the norm, and stands at the corner of Avenue Victor Hugo and Rue Antoine Zinnen. Willy Hahn of Trier redesigned the interior in 1976. |
| Facts | Built: 1910–1913<br>Architect: Nicolas Petit<br>Style: Neo-Romanesque<br>Interior renovation: 1976, Willy Hahn<br>Heritage status: national monument (2019) |
| Visiting | Open to the public during services. |
| Images | [`saint-joseph__photo.jpg`](images/saint-joseph__photo.jpg): Saint-Joseph Church, Limpertsberg |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/St_Joseph%27s_Church%2C_Limpertsberg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/St_Joseph%27s_Church%2C_Limpertsberg) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Jousefskierch_um_Lampertsbierg) |
| Pin | Saint-Joseph Church · 2 |

<a id="fondation-pescatore"></a>
### Fondation J.-P. Pescatore

| | |
|---|---|
| Local name | Fondation Jean-Pierre Pescatore |
| Coordinates | 49.61627, 6.12778 |
| Category | landmark |
| Quarter | Limpertsberg |
| About | In 1853 the banker Jean-Pierre Pescatore left Luxembourg City half a million francs to build a home for old people. The Neo-Gothic building went up in 1886–1892 on the site of the fortress's Redoute Marie, at the edge of the newly laid-out municipal park, and was the first building in Luxembourg to use reinforced concrete. It opened in 1892, has been extended with new wings several times since, and is still a care home run by the foundation. |
| Facts | Founded: 1853 (bequest of Jean-Pierre Pescatore)<br>Built: 1886–1892<br>Architect: Tony Dutreux (disputed)<br>Style: Neo-Gothic<br>Use: home for the elderly |
| Visiting | Residential care home; seen from outside only. |
| Images | [`fondation-pescatore__photo.jpg`](images/fondation-pescatore__photo.jpg): Fondation J.-P. Pescatore |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fondation_Pescatore) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fondation_Pescatore) |
| Pin | Fondation Pescatore · 2 |

<a id="hinzert-cross"></a>
### National Monument of Resistance and Deportation

| | |
|---|---|
| Local name | Monument national de la Résistance et de la Déportation / Hinzerter Kräiz |
| Coordinates | 49.61513, 6.11956 |
| Category | landmark |
| Quarter | Limpertsberg |
| About | This wooden cross in the Notre-Dame cemetery honours the 82 Luxembourgers executed at the SS camp of Hinzert and in Cologne's Klingelpütz prison who are buried here. Joseph Colabianchi, a joiner and former Hinzert prisoner, made it from planks taken from the camp's huts; it first stood at Hinzert and was raised over the graves in March 1946. In 1969 the setting was redesigned and Lucien Wercollier's bronze 'The Political Prisoner' added. It became a national monument in 1974. |
| Facts | Cross erected: March 1946<br>Maker: Joseph Colabianchi<br>Sculpture: 'The Political Prisoner' by Lucien Wercollier (1969)<br>Heritage status: national monument (1974)<br>Setting: Notre-Dame cemetery |
| Visiting | In the cemetery; open during cemetery hours. |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Hinzerter_Kr%C3%A4iz) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Hinzerter_Kr%C3%A4iz) |
| Pin | Hinzert Cross · 3 |
| Model | no |

<a id="saint-mathieu"></a>
### Saint-Mathieu Church, Pfaffenthal

| | |
|---|---|
| Local name | Église Saint-Mathieu / Kierch Pafendall |
| Coordinates | 49.61599, 6.13307 |
| Category | church |
| Quarter | Pfaffenthal |
| About | The parish church of Pfaffenthal stands by the bridge over the Alzette at the corner of Rue Saint-Mathieu and Rue Vauban. A first church with a glass dome, by the city architect Jean-François Eydt, opened in 1847, but it proved too hot in summer and too cold in winter and was replaced by the present neo-Byzantine church by state architect Charles Arendt, consecrated in 1872. During the Second World War the priest hid young men fleeing forced conscription in its tower, and since about 2020 it has been used by the Romanian Orthodox community. |
| Facts | Consecrated: 1872<br>Architect: Charles Arendt<br>Style: neo-Byzantine<br>Stained glass: about 1920<br>Use: Romanian Orthodox worship (since about 2020) |
| Visiting | Open during services. |
| Images | [`saint-mathieu__photo.jpg`](images/saint-mathieu__photo.jpg): Saint-Mathieu Church, Pfaffenthal |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Pafendall) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Pafendall) |
| Pin | Saint-Mathieu Church · 2 |

<a id="vauban-towers"></a>
### Vauban Towers

| | |
|---|---|
| Local name | Tours Vauban / Vauban-Tierm |
| Coordinates | 49.61682, 6.13245 |
| Category | fortification |
| Quarter | Pfaffenthal |
| About | Two gate towers, the Siechentor and the Eichertor, face each other across the Alzette in Pfaffenthal, joined by a defensive wall that once sealed the river and now carries a footbridge, the 'Béinchen'. After the French siege of 1684, Vauban drew the poorly defended valley into the fortress, and the towers took the names of the medieval gates that stood here. Machicolations at their base let defenders drop missiles on attackers. |
| Facts | Towers: Siechentor and Eichertor<br>Built: from 1685, under Vauban<br>Link: barrier wall over the Alzette, now a footbridge<br>Heritage status: part of the UNESCO World Heritage fortress (1994) |
| Visiting | Outside only; the footbridge between the towers is open to walkers. |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Vauban-T%C3%BCrme) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Vauban-T%C3%BCrme) |
| Pin | Vauban Towers · 1 |
| Model | no |

<a id="pfaffenthal-gates"></a>
### Eich Gate and Pfaffenthal wall

| | |
|---|---|
| Local name | Porte d'Eich / Eecherpaart |
| Coordinates | 49.61638, 6.13098 |
| Category | fortification |
| Quarter | Pfaffenthal |
| About | When Vauban took over the fortress for France, he judged the lightly defended Pfaffenthal valley a weak point, and from 1684-85 he enclosed it with a new wall and gate towers. The Eich Gate, named after the medieval gate it replaced on the road to Eich, is linked across the Alzette by a narrow wall-bridge, the Béinchen, to its twin, the Bons-Malades gate. From there the Vauban wall climbs the valley side, with a ditch and caponier uncovered during restoration and an arrow-shaped ravelin of 1743 in front of the gate. |
| Facts | Built: 1684-1685<br>Engineer: Vauban<br>Ravelin added: 1743<br>Restored: 1991 and 1998<br>Linked by: the Béinchen wall-bridge over the Alzette |
| Visiting | Outside freely visible; the Vauban Circular Walk passes by. |
| Images | [`pfaffenthal-gates__photo.jpg`](images/pfaffenthal-gates__photo.jpg): Eich Gate and Pfaffenthal wall |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Siechentor) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Siechentor) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Sichepaart) · [Luxembourg City Tourist Office](https://www.luxembourg-city.com/en/place/monument/vauban-towers) |
| Pin | Eich Gate · 2 |
| Model | no |

<a id="fort-niedergrunewald"></a>
### Fort Niedergrünewald

| | |
|---|---|
| Local name | Fort Niedergrünewald / Fort du Bas-Grünewald |
| Coordinates | 49.61630, 6.13386 |
| Category | fortification |
| Quarter | Pfaffenthal |
| About | Vauban built this large outwork in 1684–1685, after the French took Luxembourg, on the very spot where his guns had shelled the town. From the edge of the Kirchberg plateau it commanded both the plateau and the Pfaffenthal valley below. It had a moated redoubt on the slope, fronted by a crown-work of bastions. Most of it was blown up in 1874–1876; since then the redoubt, its moat and a curtain wall have been cleared and partly rebuilt, and a small lookout turret, the 'Spanish turret', survives. |
| Facts | Built: 1684–1685<br>Architect: Sébastien Le Prestre de Vauban<br>Demolished: mainly 1874–1876<br>Remains: redoubt, moat, curtain wall and a lookout turret<br>Setting: public parkland on the slope above Pfaffenthal |
| Visiting | The redoubt and moat are freely accessible; casemates by guided tour only. |
| Images | [`fort-niedergrunewald__photo.jpg`](images/fort-niedergrunewald__photo.jpg): Fort Niedergrünewald |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Niedergr%C3%BCnewald) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Niedergr%C3%BCnewald) |
| Pin | Fort Niedergrünewald · 2 |
| Model | no |

<a id="pfaffenthal-viaduct"></a>
### Pfaffenthal Viaduct

| | |
|---|---|
| Local name | Viaduc de Pfaffenthal / Pafendaller Viaduc |
| Coordinates | 49.61339, 6.13807 |
| Category | bridge |
| Quarter | Pfaffenthal |
| About | One of four railway viaducts in Luxembourg City, this bridge carries the northern line across the Alzette valley between Clausen and Pfaffenthal. It runs on from the Clausen viaduct, to which a bridge over the Montée de Clausen links it, and continues along Rue Vauban towards the Dräi Eechelen viaduct. The British contractors Waring Brothers built it from 1859, and it opened in 1862 with the line to the north. It is about 257 m long. |
| Facts | Built: 1859–1862<br>Opened: 1862<br>Builders: Waring Brothers<br>Length: 257 m<br>Use: railway line 1, Luxembourg to Troisvierges |
| Visiting | Visible from the streets of Pfaffenthal and Clausen. |
| Images | [`pfaffenthal-viaduct__photo.jpg`](images/pfaffenthal-viaduct__photo.jpg): Pfaffenthal Viaduct |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Viaduc_de_Pfaffenthal) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Viaduc_de_Pfaffenthal) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Pafendaller_Viaduc) |
| Pin | Pfaffenthal Viaduct · 3 |
| Model | no |

<a id="fort-rubamprez"></a>
### Fort Rubamprez

| | |
|---|---|
| Local name | Fort Rubamprez |
| Coordinates | 49.61061, 6.14312 |
| Category | fortification |
| Quarter | Clausen |
| About | This outwork on the Rham plateau began as a redoubt built in 1684-89 under Vauban to keep siege guns away from the city. The Austrians enlarged it in 1735 with a bastion-shaped envelope, moving the Trier road closer to Clausen. When the fortress was dismantled after 1867 the outer works and ditch disappeared, but the reduit, a powder magazine, still stands on the grounds of the National Sports Institute, where it serves as a sports hall. |
| Facts | Built: 1684-1689 (redoubt); enlarged 1735<br>Engineer: Vauban (first phase)<br>Dismantled: after 1867<br>Survives: reduit / powder magazine<br>Use: sports hall of the National Sports Institute |
| Visiting | On the grounds of the National Sports Institute; outside view only. |
| Images | [`fort-rubamprez__photo.jpg`](images/fort-rubamprez__photo.jpg): Fort Rubamprez |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Rubamprez) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Rubamprez) |
| Pin | Fort Rubamprez · 3 |

<a id="mansfeld-castle"></a>
### La Fontaine Castle ruins and Mansfeld Park

| | |
|---|---|
| Local name | Château La Fontaine / Schlass La Fontaine, Parc Mansfeld |
| Coordinates | 49.61524, 6.14430 |
| Category | park |
| Quarter | Clausen |
| About | Peter Ernst I von Mansfeld, governor of Luxembourg, began a grand Renaissance palace in Clausen in 1563 and kept enlarging it until his death in 1604. He rerouted the road to Neudorf, walled in a large hunting park and filled the gardens with Roman statues, among them a Venus fountain. The French destroyed the palace in the siege of 1684, and very little survives; the fountain basin has been excavated since 2003, and the grounds are now a park. |
| Facts | Built: 1563-1604<br>Builder: Peter Ernst I von Mansfeld<br>Destroyed: 1684, French siege<br>Remains: few ruins; excavated Venus fountain (since 2003) |
| Visiting | Public park, open during the day. |
| Images | [`mansfeld-castle__photo.jpg`](images/mansfeld-castle__photo.jpg): Historic drawing of Count Mansfeld's castle and gardens in Clausen |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/La_Fontaine_Castle) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/La_Fontaine_Castle) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Ch%C3%A2teau_La_Fontaine) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Schlass_La_Fontaine) |
| Pin | Mansfeld Park · 1 |
| Model | no |

<a id="sport-lycee"></a>
### Sportlycée

| | |
|---|---|
| Local name | Sportlycée |
| Coordinates | 49.61074, 6.14513 |
| Category | education |
| Quarter | Clausen |
| About | A state secondary school for talented young athletes, set up to combine schooling and high-level training. It began in 2007 as an annex of the Lycée Aline Mayrisch beside the National Sports Institute at Fetschenhaff, and became an independent school in 2012. Its own building, with a boarding house and canteen, went up in 2011-12 for about 11 million euros and was officially opened in February 2013. |
| Facts | Built: 2011-2012<br>Opened: 22 February 2013<br>Cost: about EUR 11 million<br>Use: secondary school for young athletes, with boarding house |
| Visiting | Outside only; a working school. |
| Images | [`sport-lycee__photo.jpg`](images/sport-lycee__photo.jpg): Sportlycée |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Sportlyc%C3%A9e) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Sportlyc%C3%A9e) · [Official site](https://portal.education.lu/sportlycee) |
| Pin | Sportlycée · 3 |

<a id="malakoff-tower"></a>
### Malakoff Tower

| | |
|---|---|
| Local name | Tour Malakoff / Malakoff-Tuerm |
| Coordinates | 49.61673, 6.14399 |
| Category | fortification |
| Quarter | Clausen |
| About | Built in 1861 on a hairpin bend of Rue Jules-Wilhelm, halfway between Clausen and Fort Thüngen, the Malakoff Tower was the last structure added to the fortress before it was dismantled after 1867. It takes its name from the Malakoff bastion at Sevastopol, fought over for months in the Crimean War, whose name became a byword for strength. The well-kept tower is now let to youth and scouting groups. |
| Facts | Built: 1861<br>Named after: the Malakoff tower at Sevastopol<br>Last building of the fortress before 1867<br>Use: let to the FNEL and LGS scout and guide groups |
| Visiting | Outside only; seen from Rue Jules-Wilhelm. |
| Images | [`malakoff-tower__photo.jpg`](images/malakoff-tower__photo.jpg): Malakoff Tower |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Malakoff-Turm_%28Luxemburg%29) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Malakoff-Turm_%28Luxemburg%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Malakoff-Tuerm_%28L%C3%ABtzebuerg%29) |
| Pin | Malakoff Tower · 2 |

<a id="fort-rumigny"></a>
### Fort Rumigny

| | |
|---|---|
| Local name | Fort Rumigny / Redoute de la Bombarde |
| Coordinates | 49.61115, 6.14565 |
| Category | fortification |
| Quarter | Clausen |
| About | Fort Rumigny began in 1688 as the Redoute de la Bombarde, a small lookout redoubt that Vauban added to the Rham Plateau to cope with stronger siege artillery. Under Austrian rule in 1735 it was wrapped in a new outer envelope, upgraded to a fort and renamed Rumigny, with walls added to either side. The original redoubt still survives as the fort's keep, in the grounds of the National Sports Institute between the Trier road and the railway. |
| Facts | Built: 1688 (redoubt), enlarged 1735<br>Engineer: Vauban<br>Also known as: Redoute de la Bombarde<br>Survives: the redoubt, in the grounds of the Institut national des sports |
| Visiting | On sports institute grounds; not generally open. |
| Images | [`fort-rumigny__photo.jpg`](images/fort-rumigny__photo.jpg): Fort Rumigny |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Rumigny) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Rumigny) |
| Pin | Fort Rumigny · 3 |
| Model | no |

<a id="rives-de-clausen"></a>
### Rives de Clausen

| | |
|---|---|
| Local name | Rives de Clausen |
| Coordinates | 49.61260, 6.14242 |
| Category | landmark |
| Quarter | Clausen |
| About | For centuries the Mousel brewery stood on the banks of the Alzette in Clausen, until brewing moved to Diekirch in 2000 after a merger with the Brasserie de Luxembourg. The old brewery halls were then turned into a lively quarter of bars, restaurants and beer houses, which opened in 2008 along a private lane, formerly Rue Émile Mousel. A microbrewery set up in the old buildings in 2007, and a footbridge crosses the river towards Rue de la Tour Jacob. |
| Facts | Former use: Mousel brewery (brewing until 2000)<br>Opened as leisure quarter: 2008<br>Microbrewery: since 2007<br>Use: bars, restaurants and nightlife |
| Visiting | Bars and restaurants open in the evenings, busiest at weekends. |
| Images | [`rives-de-clausen__photo.jpg`](images/rives-de-clausen__photo.jpg): Rives de Clausen<br>[`rives-de-clausen__photo-2.jpg`](images/rives-de-clausen__photo-2.jpg): Rives de Clausen, another view |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Rives_de_Clausen) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Rives_de_Clausen) · [Wikipedia (en)](https://en.wikipedia.org/wiki/Mousel) |
| Pin | Rives de Clausen · 1 |

<a id="sainte-cunegonde"></a>
### Saint Cunigunde Church, Clausen

| | |
|---|---|
| Local name | Église Sainte-Cunégonde / Clausener Kierch |
| Coordinates | 49.61511, 6.14329 |
| Category | church |
| Quarter | Clausen |
| About | Clausen became a parish of its own in 1865, split from Saint-Michel, and its church was built and consecrated by Bishop Nicolas Adames that same year. It stands on the Place Sainte-Cunégonde by the Allée Pierre de Mansfeld in the valley. Fully restored in 1958, it was badly damaged by fire in 1964 but repaired in time for its centenary in October 1965. Today it is known for its weekly Sunday Mass in the traditional Latin rite. |
| Facts | Built: 1865<br>Consecrated by: Bishop Nicolas Adames<br>Organ: 1875, Breidenfeld of Trier<br>Fire and repair: 1964–1965<br>Use: Catholic church, Sunday Latin Mass |
| Visiting | Open to the public during services. |
| Images | [`sainte-cunegonde__photo.jpg`](images/sainte-cunegonde__photo.jpg): Saint Cunigunde Church, Clausen |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Clausen) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Clausen) |
| Pin | Sainte-Cunégonde · 2 |

<a id="court-of-auditors"></a>
### European Court of Auditors

| | |
|---|---|
| Local name | Cour des comptes européenne |
| Coordinates | 49.62279, 6.14953 |
| Category | eu-institution |
| Quarter | Kirchberg |
| About | The European Court of Auditors checks how the European Union raises and spends its money. Set up by a 1975 treaty and at work from October 1977, it became a full EU institution under the Maastricht Treaty in 1993. Its Kirchberg seat on Rue Alcide de Gasperi centres on a main building of 1988 by the Brussels architect Paul Noël, wrapped by two street-front extensions of 2003 and 2012 by Jim Clemes, whose regular façades are picked out with thin lines of primary colour. |
| Facts | Established: 18 October 1977<br>Main building: 1988, architect Paul Noël<br>Extensions: 2003 and 2012, Jim Clemes<br>Members: one per EU member state<br>Use: EU external audit institution |
| Visiting | Working institution; the buildings are seen from outside. |
| Images | [`court-of-auditors__photo.jpg`](images/court-of-auditors__photo.jpg): European Court of Auditors |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_Court_of_Auditors) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_Court_of_Auditors) · [Luxembourg City Tourist Office](https://luxembourg-city.com/en/place/monument/european-court-of-auditors-luxembourg) · [CVCE.eu](https://www.cvce.eu/obj/building_of_the_court_of_auditors-en-be79588f-c67c-499b-a86d-97ef2dd8aeb9.html) · [Official site](https://www.eca.europa.eu/) |
| Pin | Court of Auditors · 1 |

<a id="national-library"></a>
### National Library of Luxembourg

| | |
|---|---|
| Local name | Bibliothèque nationale du Luxembourg / Nationalbibliothéik |
| Coordinates | 49.62975, 6.16523 |
| Category | culture |
| Quarter | Kirchberg |
| About | The National Library, the largest in the country, traces its roots to a school library of 1798 and took its present form in 1899. After decades in cramped premises in the old town it moved to a purpose-built home on Avenue John F. Kennedy in Kirchberg, designed by the Münster practice Bolles+Wilson after a 2003 competition and opened in October 2019. The long, low building gathers its reading room in tiers like an amphitheatre beneath a single wide-span roof. |
| Facts | Founded: 1899 (roots in 1798)<br>Current building opened: 1 October 2019<br>Architect: Bolles+Wilson<br>Holdings: about 1.8 million printed items<br>Use: national and legal-deposit library |
| Visiting | Open to the public during library opening hours. |
| Images | [`national-library__photo.jpg`](images/national-library__photo.jpg): National Library of Luxembourg |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/National_Library_of_Luxembourg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/National_Library_of_Luxembourg) · [Archello](https://archello.com/news/bolleswilson-shapes-national-library-of-luxembourg-like-amphitheatre-for-reading-under-long-span-roof) · [Official site](http://bnl.public.lu) |
| Pin | National Library · 1 |

<a id="chamber-of-commerce"></a>
### Chamber of Commerce

| | |
|---|---|
| Local name | Chambre de Commerce / Handelskummer |
| Coordinates | 49.62395, 6.14890 |
| Category | modern |
| Quarter | Kirchberg |
| About | Founded by royal decree in 1841, only two years after independence, the Chamber of Commerce is the oldest professional chamber in Luxembourg and speaks for businesses in industry, trade, finance and services. Its Kirchberg headquarters came out of an international competition won by the French architect Claude Vasconi with his Luxembourg partner Jean Petit, who renovated and greatly extended the site. The result is a sequence of six steel-and-glass blocks along Rue Alcide de Gasperi and Rue Erasme, occupied from the end of 2003. |
| Facts | Institution founded: 1 October 1841<br>Headquarters completed: 2003-2004<br>Architects: Claude Vasconi with Jean Petit<br>Design: six steel-and-glass blocks<br>Use: offices and conference centre of the Chamber |
| Visiting | Offices; open to visitors for events and conferences. |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Chambre_de_commerce_%28Luxembourg%29) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Chambre_de_commerce_%28Luxembourg%29) · [Wikipedia (de)](https://de.wikipedia.org/wiki/Handelskammer_Luxemburg) · [Luxembourg City Tourist Office](https://luxembourg-city.com/en/place/monument/luxembourgish-chamber-of-commerce) · [Official site](https://www.cc.lu/en/) |
| Pin | Chamber of Commerce · 3 |
| Interior | none |

<a id="fort-parkhohe"></a>
### Fort Parkhöhe

| | |
|---|---|
| Local name | Fort de la Hauteur du Parc / Fort Parkhéicht |
| Coordinates | 49.61679, 6.14644 |
| Category | fortification |
| Quarter | Kirchberg |
| About | Fort Parkhöhe was one of the last outworks of the Luxembourg fortress, built by the Prussian garrison in 1864-1865 on the heights above Clausen to close the gap between Fort Thüngen and Fort Dumoulin. Its core was a bomb-proof, T-shaped powder magazine behind a ditch guarded by a caponier, but it was demolished in 1867 when the fortress was dismantled. The name recalls the deer park laid out here in the 16th century by Count Peter Ernst of Mansfeld, and since 1970 the site has been occupied by the archdiocesan seminary. |
| Facts | Built: 1864-1865<br>Demolished: 1867<br>Builder: Prussian garrison of the fortress<br>Core: T-shaped bomb-proof powder magazine<br>Site today: seminary of the Archdiocese of Luxembourg (since 1970) |
| Images | [`fort-parkhohe__photo.jpg`](images/fort-parkhohe__photo.jpg): Fort Parkhöhe |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Parkh%C3%B6he) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Parkh%C3%B6he) |
| Pin | Fort Parkhöhe · 3 |
| Model | no |

<a id="eib"></a>
### European Investment Bank

| | |
|---|---|
| Local name | Banque européenne d'investissement |
| Coordinates | 49.63195, 6.16817 |
| Category | eu-institution |
| Quarter | Kirchberg |
| About | The European Union's lending bank, founded in 1958, moved to the Kirchberg plateau in 1980. Its first headquarters, a low, cross-shaped Brutalist building by Sir Denys Lasdun, was built in 1974-80, one of his few works outside Britain, and extended in 1995. Next to it rises the East Building by Ingenhoven Architekten with Werner Sobek, opened in 2008: a long office block under a vast curved glass roof, with winter gardens inside. |
| Facts | Built: 1974-1980 (West Building); East Building opened 2008<br>Architects: Denys Lasdun (West); Ingenhoven Architekten with Werner Sobek (East)<br>Style: Brutalist (West)<br>Glass roof: about 170 m by 50 m (East Building)<br>Use: headquarters of the European Investment Bank |
| Visiting | Outside only; the buildings are offices. |
| Images | [`eib__photo.jpg`](images/eib__photo.jpg): European Investment Bank |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_Investment_Bank) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_Investment_Bank) · [Official site](https://www.eib.org/en/about/headquarters) |
| Pin | EIB · 1 |

<a id="european-school"></a>
### European School Luxembourg I

| | |
|---|---|
| Local name | École européenne Luxembourg I |
| Coordinates | 49.62753, 6.15561 |
| Category | education |
| Quarter | Kirchberg |
| About | The very first European School was set up in October 1953 by parents working for the European Coal and Steel Community, starting with 72 pupils in a former furniture shop in Limpertsberg. It became officially a European School in 1957 and, after a building on Boulevard de la Foire, moved to the Kirchberg plateau in 1973. It teaches the children of EU staff and others in several language sections. |
| Facts | Founded: October 1953<br>European School status: April 1957<br>On Kirchberg since: 1973<br>Use: nursery, primary and secondary school |
| Visiting | Outside only; a working school. |
| Images | [`european-school__photo.jpg`](images/european-school__photo.jpg): European School Luxembourg I |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_School%2C_Luxembourg_I) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/European_School%2C_Luxembourg_I) · [Official site](http://www.euroschool.lu/) |
| Pin | European School · 3 |

<a id="fort-olizy"></a>
### Fort Olizy

| | |
|---|---|
| Local name | Fort Olizy / Fort Olisy |
| Coordinates | 49.61884, 6.13647 |
| Category | fortification |
| Quarter | Kirchberg |
| About | Fort Olizy was one of the outer forts guarding the Kirchberg heights across the Alzette from the old town, between today's Avenue John F. Kennedy and the European Investment Bank. It was an irregular five-sided work with its broad front facing the valley, linked to Fort Thüngen by tunnels. Of the four Kirchberg forts it is the one where only parts of the underground works survive, some damaged when the Red Bridge was built. |
| Facts | Type: irregular pentagonal outer fort<br>Remains: parts of the underground galleries only<br>Location: between Avenue J.F. Kennedy and the EIB<br>Street name: Rue du Fort Olisy in Pfaffenthal recalls it |
| Visiting | Little to see above ground; the nearby Dräi Eechelen museum at Fort Thüngen offers 3D tours of its galleries. |
| Images | [`fort-olizy__photo.jpg`](images/fort-olizy__photo.jpg): Fort Olizy |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Olizy) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Olizy) · [Musée Dräi Eechelen](https://m3e.public.lu/en/forts.html) |
| Pin | Fort Olizy · 3 |
| Model | no |

<a id="jean-monnet-2"></a>
### Jean Monnet 2 Building

| | |
|---|---|
| Local name | Bâtiment Jean Monnet 2 / Jean-Monnet-2-Gebai |
| Coordinates | 49.62453, 6.14692 |
| Category | eu-institution |
| Quarter | Kirchberg |
| About | Jean Monnet 2 is a large office complex being built by the Luxembourg state for the European Commission on Boulevard Konrad Adenauer, on part of the site of the first Jean Monnet building (1975), which was demolished in 2016-2019 after asbestos was found. Designed by KSP Jürgen Engel Architekten, it pairs a 180-metre, eight-storey block with a 24-storey tower, linked at low level, plus a welcome pavilion. Work began in 2018; the pandemic and contractor problems have pushed completion back to around 2028. |
| Facts | Status: under construction (2026)<br>Ground broken: 4 June 2018<br>Architect: KSP Jürgen Engel Architekten<br>Size: 8-storey block and 24-storey tower<br>Capacity: about 3,600 workplaces |
| Visiting | Building site; seen from outside only. |
| Images | [`jean-monnet-2__photo.jpg`](images/jean-monnet-2__photo.jpg): Jean Monnet 2 Building |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Jean_Monnet_2_building) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Jean_Monnet_2_building) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Jean-Monnet-2-Gebai) · [Fonds Kirchberg](https://fondskirchberg.public.lu/en/projets/lieux-de-travail/jmo2.html) |
| Pin | Jean Monnet 2 · 2 |

<a id="kinepolis"></a>
### Kinepolis Kirchberg

| | |
|---|---|
| Local name | Kinepolis Kirchberg |
| Coordinates | 49.63370, 6.17277 |
| Category | culture |
| Quarter | Kirchberg |
| About | Opened in 1996 as Utopolis Kirchberg, this multiplex on Avenue John F. Kennedy is the largest cinema in Luxembourg, with ten screens and about 2,500 seats. It took its present name after the Belgian Kinepolis Group bought the Utopia Group at the end of 2015. It sits east of the Kirchberg district centre, amid the plateau's offices and shopping streets. |
| Facts | Opened: 1996<br>Former name: Utopolis Kirchberg<br>Screens: 10<br>Seats: 2,505<br>Operator: Kinepolis Group (since 2015) |
| Visiting | Open daily for film screenings. |
| Images | [`kinepolis__photo.jpg`](images/kinepolis__photo.jpg): Kinepolis Kirchberg |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Kinepolis_Kirchberg) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Kinepolis_Kirchberg) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Kinepolis_Kirchberg) · [Official site](https://kinepolis.lu/en/bioscopen/kinepolis-kirchberg/info) |
| Pin | Kinepolis · 3 |

<a id="schuman-building"></a>
### Robert Schuman Building

| | |
|---|---|
| Local name | Bâtiment Robert Schuman / Robert-Schuman-Gebai |
| Coordinates | 49.61815, 6.14122 |
| Category | eu-institution |
| Quarter | Kirchberg |
| About | Built between 1970 and 1973 on the Place de l'Europe to designs by Laurent Schmit, this state-owned block was made for the services of the European Parliament and an assembly chamber. Plans grew during construction when three new member states joined. The chamber, with a geometric zinc relief by the Italian group NP2, hosted 35 Parliament sittings in 1973–1979 but was too small after the 1979 elections; Parliament offices remained in the building. |
| Facts | Built: 1970–1973<br>Architect: Laurent Schmit<br>Height: about 35 m<br>Owner: Luxembourg State<br>Use: European Parliament offices; former assembly chamber |
| Visiting | Office building; seen from outside only. |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Robert-Schuman-Gebai) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Robert-Schuman-Gebai) |
| Pin | Schuman Building · 3 |

<a id="hemicycle"></a>
### European Convention Center Luxembourg

| | |
|---|---|
| Local name | European Convention Center Luxembourg (ECCL) / Hémicycle |
| Coordinates | 49.61841, 6.14609 |
| Category | eu-institution |
| Quarter | Kirchberg |
| About | Luxembourg's main conference centre lies along the south side of the Place de l'Europe, at the foot of the Alcide De Gasperi tower. Its core is the Hémicycle, a debating chamber built in 1978–1979 after a grander parliament project was dropped, where the European Parliament sat until 1981. A long, low modern wing about 300 m long, designed by Schemel & Wirtz with Jourdan-Müller/PAS, now links it to the tower. The Council of the EU meets here each April, June and October. |
| Facts | Hémicycle opened: 1979<br>European Parliament sittings: 1979–1981<br>Architects of the convention centre: Schemel & Wirtz with Jourdan-Müller/PAS<br>Size: about 300 m long, 10 m high<br>Hémicycle seats: 646<br>Use: Council of the EU meetings and conferences |
| Visiting | Open for conferences and events only. |
| Images | [`hemicycle__photo.jpg`](images/hemicycle__photo.jpg): European Convention Center Luxembourg |
| Sources | [Official site](https://eccl.lu) · [Fonds Kirchberg](https://fondskirchberg.public.lu/en/vivre-kirchberg/travailler-etudier/foires-conferences/eccl.html) · [Europeana: The Hemicycles](https://europeana.eu/en/exhibitions/the-hemicycle/the-hemicycles-luxembourg) · [Luxembourg City Tourist Office](https://www.luxembourg-city.com/en/place/monument/european-convention-center-luxembourg) |
| Pin | ECCL / Hémicycle · 2 |

<a id="luxexpo"></a>
### Luxexpo The Box

| | |
|---|---|
| Local name | Luxexpo The Box |
| Coordinates | 49.63528, 6.17172 |
| Category | culture |
| Quarter | Kirchberg |
| About | Luxembourg's exhibition and congress centre on the Kirchberg plateau goes back to trade fairs held from the 1920s, which moved from the Limpertsberg halls to Kirchberg in 1974. The halls were renamed Luxexpo in 2004 and, after a refurbishment, Luxexpo The Box in 2017. A congress centre fitted out in 2003–2004 by architect Jim Clemes, to host EU ministers' meetings while their usual building was rebuilt, won a national architecture prize. Its halls host the spring and autumn fairs. |
| Facts | On Kirchberg since: 1974<br>Renamed Luxexpo: 2004<br>Renamed Luxexpo The Box: 2017<br>Congress centre: 2003–2004, architect Jim Clemes<br>Facilities: seven halls and several rooms<br>Use: trade fairs, congresses and events |
| Visiting | Open during fairs and events. |
| Images | [`luxexpo__photo.jpg`](images/luxexpo__photo.jpg): Luxexpo The Box |
| Wikipedia | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Luxexpo_The_Box) |
| Sources | [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Luxexpo_The_Box) · [Wikipedia (de)](https://de.wikipedia.org/wiki/Luxexpo) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Luxexpo) · [Official site](https://thebox.lu/) |
| Pin | Luxexpo The Box · 2 |

<a id="weimerskirch-church"></a>
### Saint-Martin Church, Weimerskirch

| | |
|---|---|
| Local name | Église Saint-Martin / Kierch Weimeschkierch |
| Coordinates | 49.62784, 6.13509 |
| Category | church |
| Quarter | Weimerskirch |
| About | Weimerskirch is one of the oldest parishes in the country, mentioned around 723 in a document of the Abbey of St Maximin in Trier, and is often called the mother parish of Luxembourg City. The present church of St Martin dates mainly from 1763-64 and was consecrated in 1767 by the Trier auxiliary bishop Johann Nikolaus von Hontheim; it was enlarged in the late 19th century. A terraced churchyard lies beside it on several levels. |
| Facts | Built: 1763-1764<br>Consecrated: 1767<br>Patron: St Martin<br>Heritage status: national monument (2019)<br>Use: Catholic church |
| Visiting | Open to the public during services. |
| Images | [`weimerskirch-church__photo.jpg`](images/weimerskirch-church__photo.jpg): Saint-Martin Church, Weimerskirch |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Weimeschkierch) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Weimeschkierch) |
| Pin | Weimerskirch Church · 3 |

<a id="dommeldange-church"></a>
### Saint-Hubert Church, Dommeldange

| | |
|---|---|
| Local name | Église Saint-Hubert / Haupeschkierch Dummeldeng |
| Coordinates | 49.63397, 6.13833 |
| Category | church |
| Quarter | Dommeldange |
| About | Dommeldange's Catholic church dates from 1891, when it replaced a chapel of 1777, and is dedicated to St Hubert of Liège, whose feast falls on 3 November. It was restored in 1949, given a crucifixion scene by Hans Lechner in 1951, and reordered in 1970-72 to follow the Second Vatican Council. It stands at the junction of Rue du Château and Rue des Hauts-Fourneaux, with the St Hubert fountain in the square before it. |
| Facts | Built: 1891<br>Replaced: chapel of 1777<br>Patron: St Hubert<br>Restored: 1949; interior renovated 1984-85<br>Artwork: crucifixion scene by Hans Lechner (1951) |
| Visiting | Open to the public during services and church events. |
| Images | [`dommeldange-church__photo.jpg`](images/dommeldange-church__photo.jpg): Saint-Hubert Church, Dommeldange |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Hubertuskirche_%28Dommeldingen%29) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Hubertuskirche_%28Dommeldingen%29) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Haupeschkierch_vun_Dummeldeng) |
| Pin | Saint-Hubert Church · 3 |

<a id="pulvermuhl-viaduct"></a>
### Pulvermühl Viaduct

| | |
|---|---|
| Local name | Viaduc de Pulvermühl / Biisserbréck |
| Coordinates | 49.60785, 6.13931 |
| Category | bridge |
| Quarter | Pulvermühl |
| About | This railway viaduct carries the lines north of Luxembourg station across the Alzette valley at Pulvermühl, towards the Rham plateau and on to Trier and the north of the country. Like the city's other early viaducts, it was built to plans by the Waring Brothers and opened with the railway in the early 1860s. It runs for 242 metres and stands up to 37 metres high; it was electrified in 1988, and in 2019 a second viaduct alongside raised the crossing from two tracks to four. |
| Facts | Opened: 1861-1862<br>Engineers: Waring Brothers<br>Length: 242 m<br>Height: up to 37 m<br>Electrified: 1988<br>Second viaduct: inaugurated 11 June 2019 |
| Visiting | Railway structure; best seen from the Alzette valley below. |
| Images | [`pulvermuhl-viaduct__photo.jpg`](images/pulvermuhl-viaduct__photo.jpg): The arches of the Pulvermühl viaduct |
| Wikipedia | [Wikipedia (en)](https://en.wikipedia.org/wiki/Pulvermuhl_Viaduct) |
| Sources | [Wikipedia (en)](https://en.wikipedia.org/wiki/Pulvermuhl_Viaduct) · [Wikipedia (fr)](https://fr.wikipedia.org/wiki/Viaduc_de_Pulverm%C3%BChl) |
| Pin | Pulvermühl Viaduct · 1 |
| Model | no |

<a id="schlaifmillen"></a>
### Schläifmillen

| | |
|---|---|
| Local name | Schläifmillen / Schleifmühle |
| Coordinates | 49.60804, 6.16118 |
| Category | culture |
| Quarter | Hamm |
| About | Once a small mill on the Alzette where iron and metal goods were ground, the Schläifmillen was bought by the brothers Samson and Guetschlique Godchaux and became the heart of their woollen cloth works, later powered by steam. For many years it was also the administrative centre of the old commune of Hamm. Production stopped in 1939, and from the 1980s artists and designers moved into the old mill buildings in the valley. |
| Facts | Original use: grinding mill<br>Later use: Godchaux Frères cloth factory<br>Production ended: 1939<br>Use since the 1980s: artists' studios |
| Visiting | Outside only, except during occasional open studios and events. |
| Images | [`schlaifmillen__photo.jpg`](images/schlaifmillen__photo.jpg): Schläifmillen |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Schl%C3%A4ifmillen_%28L%C3%ABtzebuerg%29) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Schl%C3%A4ifmillen_%28L%C3%ABtzebuerg%29) · [Chronicle.lu: industrial heritage](https://chronicle.lu/category/at-home/52056-industrial-heritage-textiles-in-luxembourg) |
| Pin | Schläifmillen · 3 |

<a id="hamm-church"></a>
### Church of the Exaltation of the Holy Cross, Hamm

| | |
|---|---|
| Local name | Église de l'Exaltation-de-la-Sainte-Croix / Kierch Hamm |
| Coordinates | 49.61024, 6.16764 |
| Category | church |
| Quarter | Hamm |
| About | Hamm's parish church sits at a crossroads of four streets. A church here is first recorded in 1337, serving a community of hermit women, and later drew pilgrims to a miraculous cross. In 1902–1903 the old church was replaced by a Neo-Gothic building, but its 14th-century choir and the tower beside it on the north side were kept and built into the new church, so the old and new parts can still be told apart. |
| Facts | First recorded: 1337<br>Rebuilt: 1902–1903<br>Style: Neo-Gothic, with a 14th-century choir<br>Parish since: 1867<br>Dedication: Exaltation of the Holy Cross |
| Visiting | Open to the public during services. |
| Images | [`hamm-church__photo.jpg`](images/hamm-church__photo.jpg): Church of the Exaltation of the Holy Cross, Hamm |
| Wikipedia | [Wikipedia (de)](https://de.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Hamm) |
| Sources | [Wikipedia (de)](https://de.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Hamm) · [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Hamm) |
| Pin | Hamm Church · 3 |

<a id="cents-church"></a>
### Holy Spirit Church, Cents

| | |
|---|---|
| Local name | Église du Saint-Esprit / Kierch Zens |
| Coordinates | 49.61561, 6.15970 |
| Category | church |
| Quarter | Cents |
| About | One of the youngest and most modern churches in the city, the Holy Spirit Church stands at the junction of Rue de Trèves and Boulevard Charles Simonis. Its foundation stone was laid in 1976 and Bishop Jean Hengen consecrated it at Whitsun 1980. Designed by the architects Michel Mousel and Edouard Stein to suit the post-Vatican II liturgy, the church is lit by slab-glass windows in white, yellow and amber by the artist Théo Kerg, who also made its altar and furnishings. |
| Facts | Foundation stone: 15 May 1976<br>Consecrated: 25 May 1980<br>Architects: Michel Mousel and Edouard Stein<br>Windows and furnishings: Théo Kerg<br>Style: modern, post-Vatican II |
| Visiting | Open during services. |
| Images | [`cents-church__photo.jpg`](images/cents-church__photo.jpg): Holy Spirit Church, Cents |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Zens) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Zens) |
| Pin | Holy Spirit Church · 3 |

<a id="fort-dumoulin"></a>
### Fort Dumoulin

| | |
|---|---|
| Local name | Fort Dumoulin / Fort du Moulin |
| Coordinates | 49.61317, 6.15080 |
| Category | fortification |
| Quarter | Cents |
| About | First thrown up as a temporary arrow-shaped work during the French siege of 1794–1795 and known as Fort Fetschenhof, this outwork on the Rham plateau was rebuilt in 1836–1838 with a deep moat and soon altered again. It was renamed after Friedrich Dumoulin, an infantry general and commander of the fortress. A fortified powder magazine was added in its courtyard in 1829. Today the site is the headquarters of the Luxembourg Girl Guides association. |
| Facts | First built: 1794–1795 (temporary work)<br>Rebuilt: 1836–1838<br>Named after: General Friedrich Dumoulin<br>Use: headquarters of the Luxembourg Girl Guides (AGGL)<br>Heritage status: supplementary inventory (2012) |
| Visiting | Private site; seen from outside only. |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Dumoulin) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Fort_Dumoulin) |
| Pin | Fort Dumoulin · 3 |
| Model | no |

<a id="neudorf-church"></a>
### Saint-Henri Church, Neudorf

| | |
|---|---|
| Local name | Église Saint-Henri / Kierch Neiduerf |
| Coordinates | 49.62173, 6.16254 |
| Category | church |
| Quarter | Neudorf |
| About | Neudorf's Catholic church, dedicated to Saint Henry, stands on the Ale Wee, a small lane off the main Rue de Neudorf. It was built in stages between 1899 and 1914, with the main structure finished in 1901. Its stained-glass windows are by the Luxembourg artist Emile Probst. |
| Facts | Built: 1899–1914 (main structure 1901)<br>Architect: Kemp (attributed)<br>Windows: Emile Probst<br>Use: Catholic church |
| Visiting | Open to the public during services. |
| Images | [`neudorf-church__photo.jpg`](images/neudorf-church__photo.jpg): Saint-Henri Church, Neudorf |
| Wikipedia | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Neiduerf) |
| Sources | [Wikipedia (lb)](https://lb.wikipedia.org/wiki/Kierch_L%C3%ABtzebuerg-Neiduerf) · [Ons Stad no. 18 (1985)](https://onsstad.vdl.lu/fileadmin/uploads/media/ons_stad_18-1985_15.pdf) |
| Pin | Saint-Henri Church · 3 |
