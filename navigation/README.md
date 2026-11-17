# Matebot: Einlernen · Sperrzonen · Ziele

Eigenständige ROS-2-Jazzy-Anwendung für den vorhandenen Raspberry Pi 4. Der alte
Checkout bleibt erhalten; die laufende Installation liegt unter
`/home/matebot/develop/matebot-navigation`.

**[Oberfläche öffnen](http://matebot.local:8080)** · kein Cloud-Dienst, alle Assets lokal.

## Motoren selbst abstimmen

**[Motor-Testbereich öffnen](http://matebot.local:8080/motors)** oder das Zahnrad
in der Fahransicht wählen. Zieltakt, Beschleunigung, Pulsanteil,
Einschaltwartezeit, Anlauftakt und Anlaufphase sind einstellbar.
Eine Richtung gedrückt halten; Loslassen oder STOPP beendet den Versuch.
Zusätzlich endet er nach der gewählten Dauer von 0,25 bis 3 Sekunden.

„Entwurf speichern“ bewahrt die Kombination für den nächsten Besuch.
„Als Fahrprofil übernehmen“ übernimmt Grenzen und Anlauf für den normalen
Joystick und nach Neustarts. Normale Geschwindigkeitsgrenzen gelten weiter.
Ohne Übernahme bleibt die bisherige 100-Hz-Begrenzung aktiv.
Details zu Verhalten und Prüfung: [MOTOR_TUNING.md](MOTOR_TUNING.md).

## Aktueller Fahrstand

Die Motoren laufen vorläufig im sehr langsamen Testbetrieb: maximal 100 Hz pro
Rad (nominal etwa 3,9 mm/s geradeaus), mit einer Sekunde Anlauf bei bis zu 40 Hz.
Ein voller Joystickausschlag bleibt auf diesen gemessenen Bereich begrenzt.
Höhere Taktraten führten im realen LiDAR-/Gyro-Test weiterhin zum Stocken; normale
Fahrgeschwindigkeit und autonome Ankunft sind noch nicht nachgewiesen.

## Handy: Kamera und Joystick

**[Fahransicht öffnen](http://matebot.local:8080/drive)**. Auf kleinen Displays
öffnet sich diese Ansicht auch automatisch; **Karte** wechselt zur Grundrissansicht.
Oben zeigt die Fahransicht dieselbe echte SLAM-Hauskarte wie die große
Kartenansicht: Wände, bekannte freie Flächen, Sperrzonen, Roboterposition und
aktuelle Laserpunkte. Neue Kartenstände erscheinen laufend (SLAM etwa alle zwei
Sekunden). In der Fahransicht zeigt der Roboter immer nach oben; die Karte samt
Laserpunkten dreht sich um ihn. Die große Kartenansicht bleibt am Haus ausgerichtet. **Ganzes Haus** passt die wachsende Karte automatisch ein, +/−
zoomen, Ziehen verschiebt. Die drei zusätzlichen Entfernungen beziehen sich auf
den LiDAR, nicht auf den freien Abstand zur Stoßstange.

Darunter läuft die Frontkamera. Der Joystick unten fährt vorwärts/rückwärts und
dreht links/rechts. **Links versetzen** und **Rechts versetzen** bewegen den Roboter
seitlich ohne Drehung. Joystick und eine Seitwärtstaste können gleichzeitig gehalten
werden; die kombinierte Geschwindigkeit bleibt begrenzt. Loslassen, Wechsel zur
Karte, ein Hintergrund-Tab oder **STOPP** beenden die Bedienung. Ein über 1,2 s
nicht erneuertes Kamerabild stoppt die Fahransicht und sperrt ihre Steuerung.
Ein neuer bewusster Joystick- oder Tastendruck übernimmt die Steuerung automatisch.
Es gibt keinen Freigabedialog. Die manuelle Fahrt läuft während des Haltens
kontinuierlich mit standardmäßig 6 cm/s, einstellbar 2–12 cm/s und bis 0,4 rad/s; die frühere 160-Schritte-
Impulsbegrenzung ist ausgeschaltet. Der Zielmodus behält seine vier Bodenprüfungen.

Die CSI-Kamera liefert 640 × 360 mit bis zu 12 Bildern/s; im Browser wurden 8–10
Bilder/s beobachtet. `camera_rotation: 180` richtet die kopfüber montierte OV5647
auf. Der separate Hostdienst öffnet die Kamera bei Bedarf und schließt sie nach
vier Sekunden ohne Bildabruf. Bilder bleiben im RAM. Port 8082 ist nur an Loopback
gebunden; der Browser bezieht Bilder über denselben lokalen Webserver wie die UI.

## Erste Verwendung zu Hause

1. Roboter auf ebenen Boden stellen, Fahrbereich frei halten und Treppen physisch
   absichern. Die Motoren sind beim Start immer gesperrt.
2. **Einlernen** wählen. Für einen neuen Grundriss **Neue Karte beginnen** anklicken.
   Alte Karten werden archiviert. Vorhandene Karten werden automatisch geladen;
   der Roboter sucht seine Position durch Abgleich des LiDAR-Scans mit der Karte.
3. Joystick oder Bildschirmtasten halten; WASD bewegt, Q/E dreht. Kein Freigeben
   erforderlich. Loslassen oder Leertaste stoppt. Nach STOPP startet erst eine
   neue bewusste Eingabe wieder eine Fahrt.
4. Die individuellen Rad-Richtungen sind geprüft; reale Bodenstrecke, Seitwärtsfahrt
   und Drehung noch nicht vollständig. Deshalb bleibt die manuelle Geschwindigkeit
   niedrig, aber die Fahrt wird nicht mehr nach einem kurzen Prüfimpuls beendet.
5. Unter **Fahrprüfung & Einstellungen** nur selbst geprüfte Ergebnisse bestätigen:
   Vorwärts/Rückwärts samt Strecke, Seitwärtsfahrt, Drehung/Kartenrichtung und
   Stoppverhalten. Erst nach allen vier Prüfungen steht der autonome Zielmodus bereit.
6. Langsam durchs Erdgeschoss fahren. SLAM erweitert die Karte dabei laufend.
   **Karte speichern** schreibt sofort; ansonsten wird alle 30 Sekunden gesichert.

Das Tempo ist eine aus den Schritten berechnete Schätzung. Radencoder sind nicht
bekannt; Schlupf und ausgelassene Motorschritte müssen am realen Fahrzeug beurteilt
werden. Das System ist noch nicht als unbeaufsichtigter autonomer Roboter erprobt.

## Raster und Sperrzonen

**Sperrzonen** stoppt die Steuerung. Mit **Sperren** Zellen anklicken oder ein
Rechteck ziehen, mit **Freigeben** wieder entfernen. Rastergrößen: 10, 25, 50 oder
100 cm. Ein Rasterwechsel deckt vorhandene Sperrflächen konservativ ab, anstatt
sie zu löschen. Änderungen sind unmittelbar dauerhaft gespeichert.

Die Zellen beziehen sich auf den festen Karten-Koordinatenursprung (auch bei
negativen Koordinaten); sie verrutschen nicht, wenn die SLAM-Karte größer wird.
Auf `/map` veröffentlicht die Brücke eine Kopie der echten `/slam_map` mit den
Sperrzellen als Hindernissen. Globale **und** lokale Costmaps benutzen diese Karte.
Ein zusätzlicher Fahrwächter prüft die Roboterfläche und die vorausberechnete
Bewegung gegen dieselben Sperrzellen, auch bei manueller Steuerung. Der rohe
SLAM-Grundriss bleibt von den Sperrzonen getrennt.

Die Anzeige zeigt die gewählte Zellengröße. Die eigentliche SLAM-Karte hat 5 cm
Auflösung. Sperrzonen benötigen eine korrekte Roboterposition. Treppen müssen
physisch abgesichert bleiben: Ein waagerechter LiDAR erkennt Absturzkanten nicht
zuverlässig, und Positionsfehler können eine digitale Grenze verschieben.

## Ziele und Favoriten

**Ziele** wählen und eine bekannte freie Stelle antippen. Direktes Ziehen von der
Zielposition in eine Richtung setzt bereits den Ankunftswinkel. Im Popup kann der
Pfeil auf der vergrößerten Kartenansicht gezogen oder die Ausrichtung mit dem
Regler gradweise verändert werden. Ein Umriss zeigt die Roboterfläche, eine
gestrichelte Kontur den benötigten Platz einschließlich Ankunftstoleranz. Vor
dem Start prüft der Server Karte, aktuelle Hindernisse und Sperrzonen für die
gesamte Zielausrichtung. Unbekannte oder zu enge Bereiche werden mit einem
konkreten Hinweis abgelehnt. **Verschieben** schaltet die Karte bei Bedarf
auf Schieben statt Zielsetzen; am Computer funktioniert auch Shift + Ziehen.

**Losfahren** wartet auf eine aktive Nav2-Navigation und plant dann den Weg um
Wände, Hindernisse und Sperrzonen. Das Popup bleibt offen: Livekamera, Fahrtstatus,
verbleibende Wegstrecke und STOPP sind direkt sichtbar. Schließen oder Escape stoppt
eine laufende oder noch vorbereitete Fahrt. Nicht erreichbare Ziele zeigen einen
Fehler im Popup. Es wird kein Weg durch unbekannte Kartenbereiche geplant.

Die vier Bodenprüfungen bleiben Voraussetzung für autonome Fahrt. Unter
**Dieses Ziel speichern** werden Name, Position und Blickrichtung gespeichert;
ältere Favoriten ohne Winkel bleiben nutzbar. Nach Ankunft kann dieselbe Position
mit anderer Blickrichtung erneut angefahren werden.

## Speicherung / Wiederanlauf

- `data/session.json`: Karten-ID, Name, Betriebsart, Raster, Sperrzellen, Favoriten,
  Prüfstand. Atomarer Austausch mit `fsync`; beschädigte Zonendaten werden niemals
  stillschweigend durch leere Zonen ersetzt.
- `data/runtime.json`: letzte bekannte Position und Sicherungszeit, getrennt vom
  Karteninhalt. Eine gespeicherte Position ist keine garantierte neue Lokalisierung.
- `data/map-*`: vollständige Snapshots mit SLAM-Posegraph, Sensordaten, Rohkarte,
  PGM/YAML, Metadaten, Pose und SHA-256-Prüfsummen. `data/current` verweist atomar
  auf einen vollständig geschriebenen Snapshot. Je aktive Karte werden 20
  Revisionen aufbewahrt; archivierte Karten bleiben getrennt erhalten.
- Beim normalen Herunterfahren stoppt PID 1 zuerst die Motoren und sichert die
  Karte, **bevor** ROS beendet wird. Bei plötzlichem Stromverlust bleibt die letzte
  vollständig geschriebene Sicherung erhalten; die letzten bis zu 30 Sekunden
  Kartierung können fehlen. Ein hartes Abschalten garantiert keine fehlerfreie
  Hardware oder kein beschädigtes Dateisystem.
- Die Oberfläche zeigt nach Neustart die gespeicherte Karte, Zonen und Favoriten.
  Ein globaler Scan-Karten-Abgleich sucht die Position einschließlich Blickrichtung.
  Drei übereinstimmende Messungen müssen genügend Wandtreffer, bekannte freie
  Strahlen und Abstand zur zweitbesten Hypothese liefern. Erst dann wird der
  Posegraph an der gefundenen Position fortgesetzt. Der gespeicherte letzte Ort
  ist nur ein zusätzlicher Kandidat. Bei mehrdeutiger Umgebung läuft die Suche
  im Stand weiter; die alte Karte wird nicht überschrieben. Optional ist unter
  Einstellungen eine Positionskorrektur verfügbar.

## Sicherung und Wiederherstellung

**Sicherung laden** lädt ein `.tar.gz` auf das bedienende Gerät herunter. Enthalten
sind der aktuelle Grundriss/Posegraph und die zuletzt gespeicherten Zonen und
Favoriten. Diesen Download zusätzlich zum Pi aufbewahren.

Zum Wiederherstellen das Archiv auf den Pi kopieren und dort ausführen:

```sh
cd /home/matebot/develop/matebot-navigation
sudo systemctl stop matebot-navigation.service
sudo docker compose stop
sudo python3 restore_backup.py /pfad/zur/matebot-sicherung.tar.gz --confirm
sudo systemctl start matebot-navigation.service
```

Der Wiederhersteller akzeptiert nur definierte reguläre Dateien, prüft Karten-ID
und Prüfsummen und verwirft Pfad-Traversal, Links und doppelte Einträge. Vorhandene
Snapshots bleiben erhalten. Nach Wiederherstellung beginnt die automatische Ortung.

## Installation / Autostart

Voraussetzungen auf dem bestehenden Pi: Docker/Compose und laufendes `pigpiod`.
Auf diesem Debian-System wurden `docker.io` und `docker-compose` verwendet.
Für die Kamera zusätzlich die Hostpakete `python3-picamera2` und `python3-yaml`
installieren. Der Benutzer `matebot` benötigt Zugriff auf `video` und `render`.

```sh
cd /home/matebot/develop/matebot-navigation
sudo docker compose build
sudo cp matebot-navigation.service /etc/systemd/system/
sudo cp matebot-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now matebot-camera.service
sudo systemctl enable --now matebot-navigation.service
```

Bei anderem Installationsort die Pfade in der Service-Datei anpassen. Der Service
wartet beim Boot auf den LiDAR unter seiner stabilen USB-ID, I²C und `pigpiod`.
Docker und pigpiod müssen aktiviert bleiben. Die alten `matebot.service` und
`matebot-watchdog.service` bleiben deaktiviert. Es darf nur einen Motorcontroller
geben. Kein Internet-Portforwarding für die LAN-Oberfläche einrichten.

Quellcode und Konfiguration sind read-only in den Container eingebunden. Nach
Änderungen `sudo systemctl restart matebot-navigation.service`. Bei geänderten
Abhängigkeiten vorher `sudo docker compose build`. Daten liegen separat unter
`./data`; sie werden weder ins Image noch ins Git-Repository gepackt.
Nach Änderungen an Kamera oder ihrer Konfiguration zusätzlich
`sudo systemctl restart matebot-camera.service` ausführen.

## Hardware / Sicherheitsverhalten

Raspberry Pi 4 (4 GB), LD19 an CP2102, MPU6050 an I²C 0x68, CSI-OV5647. Vom Besitzer
gemessen: 41 × 30 cm, Radstand 31 cm, Spurweite 21 cm, LiDAR mittig 14 cm hoch.
Richtungsfaktoren in Reihenfolge FL/FR/BL/BR: `[-1, 1, -1, 1]`. Die Richtungen
wurden einzeln aufgebockt bestätigt. Front-Kartonvergleich ergab LiDAR-Yaw `-pi/2`.
200 Schritte/Umdrehung, 32 Mikroschritte und 79 mm Räder stammen aus der bisherigen
Hardwarebeschreibung; ihre reale Fahrstrecke ist noch am Boden zu prüfen.

Chassis-Nahreflexionen innerhalb der Kontur plus 4 cm werden als unbekannte
Laserstrahlen behandelt, niemals als Freiraum. Der konservative Nav2-Kreis
umschließt diese Fläche. Der MPU6050 misst die Z-Achse (Register 0x47); sein Bias
wird bei stillstehendem Start neu bestimmt.

Eine kurzlebige Steuerungskennung gehört genau einem Browser. Andere Leser
verlängern sie nicht. Die Steuerungskennung verfällt nach 2,5 s ohne gültiges Paket; manuelle
Bewegungsbefehle verfallen bereits nach 500 ms. Sequenznummern verhindern, dass verspätete Fahrbefehle ein
Loslassen überholen. Die Standardansteuerung (`motor_output: pwm`) erzeugt
durchgehendes pigpio-PWM mit 50 % Tastverhältnis. Unveränderte Fahrbefehle starten
den Takt nicht neu. Ein Skript im GPIO-Dienst stoppt alle vier Ausgänge nach etwa
300 ms ohne Steuerungsaktualisierung, auch bei Ausfall des Python-Controllers.
STOPP wartet auf die bestätigte Nullausgabe. Diskrete PWM-Frequenzen werden unter
Einhaltung der Geschwindigkeitsgrenzen gewählt; die Soll-Odometrie berücksichtigt
diese Frequenzen. `motor_output: wave` aktiviert die bisherige Wellenansteuerung.
Stale Sensoren, ungültige Position, Hindernisse und Sperrzonen
sperren die Ausgabe. Diese Software ersetzt keinen physischen Not-Aus.

## Prüfungen

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
node --check web/app.js
node --check web/drive_ui.js
node --test tests/drive_math.test.js
# Im ROS-Container, mit gefälschtem GPIO und isolierter Domain:
sudo docker exec -e ROS_DOMAIN_ID=143 matebot-navigation bash -c \
  'source /opt/ros/jazzy/setup.bash && python3 /app/tests/ros_safety_check.py'
# Echter Nav2-Planer, künstliche Karte, KEIN Motorcontroller:
sudo docker run --rm --network host -e ROS_DOMAIN_ID=144 -e ROS_LOCALHOST_ONLY=1 \
  -v "$PWD:/app:ro" matebot-navigation:local bash -c \
  'source /opt/ros/jazzy/setup.bash && python3 /app/tests/nav2_planner_check.py'
```

Der isolierte Planertest verlangt einen Weg um eine Wand durch eine Tür. Eine
Raster-Sperrzone schließt danach die Tür; der Planer muss den Weg verweigern.
Das ist ein Softwaretest und kein Nachweis einer realen autonomen Bodenfahrt.
Siehe [VERIFICATION.md](VERIFICATION.md) für tatsächliche Hardware-Prüfungen.

`wheel_test.py --wheel FL --raised` (auch FR/BL/BR) ist nur für explizit bestätigte,
stabil aufgebockte Tests mit freidrehenden Rädern. Der Container muss dabei aus
sein. Diese Tests wurden während der ersten Einrichtung mit dem Besitzer benutzt.

## Upstream

`config/nav2.upstream.yaml`: `ros-navigation/navigation2`, Jazzy,
`nav2_bringup/params/nav2_params.yaml`, Apache-2.0.
`config/slam.upstream.yaml`: `SteveMacenski/slam_toolbox`, Jazzy,
`config/mapper_params_online_async.yaml`, LGPL-2.1. Original-Lizenztexte sind
beigefügt. `configure.py` erzeugt die für dieses Fahrzeug abgeleiteten Parameter.

### Manuelles Fahren bei Hindernissen

Ein wiederholt beobachteter Eigenreflex vorne bei (0,236 m, −0,012 m) liegt
innerhalb der 4-cm-Chassismaske und wird als unbekannter Strahl ausgefiltert.
Der Navigationsradius umschließt weiterhin die gesamte maskierte Kontur.
Ein echtes Hindernis stoppt nur die betroffene manuelle Fahrtrichtung; die
Steuerungskennung bleibt erhalten, damit Rückwärts-/Seitwärts-Ausweichen möglich
ist. Der nächste aktuelle Fahrbefehl wird erneut gegen die Messung geprüft.
Akzeptierte Fahrpakete erneuern selbst die 2,5-s-Verbindung; separate Heartbeats
halten sie auch im Stillstand. Der Browser begrenzt bewegende Anfragen auf eine
laufende Anfrage, sendet Loslassen sofort mit höherer Sequenznummer und ignoriert
Fehler aus bereits überholten Steuerungssitzungen. Ohne neue Fahrpakete bleibt
der bisherige 500-ms-Motorstopp unverändert.

### Lastverteilung und manuelle Ortung

Der Motortakt läuft in einem eigenen 20-ms-Thread, unabhängig vom ROS-Executor.
SLAM bleibt beim Einlernen aktiv. Nav2 wird erst im geprüften Zielmodus gestartet
und beim Wechsel zurück beendet, statt während der Handsteuerung unnötig CPU zu
belegen. Statusabrufe warten nicht mehr auf den größeren Kartenabruf.
Eine veraltete globale Kartenposition sperrt die Handsteuerung nur, wenn gespeicherte
Sperrzonen von dieser Position abhängen; LiDAR-, IMU- und Hinderniswächter gelten
weiter. Die autonome Navigation erfordert immer eine gültige Kartenposition.
Ein einzelner fehlgeschlagener Heartbeat verwirft keine ansonsten durch aktuelle
Fahrpakete bestätigte Sitzung.
