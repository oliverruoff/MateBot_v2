# MateBot v2

Lokale Hauskartierung und Navigation für den Raspberry Pi 4 mit LD19, MPU6050
und vier Mecanum-Rädern. Die aktuelle Anwendung liegt unter **[navigation/](navigation/README.md)**.

**Oberfläche im Heimnetz: [http://matebot.local:8080](http://matebot.local:8080)**

**[Handy-Fahransicht mit Kamera und Joystick](http://matebot.local:8080/drive)**:
LiDAR in Blickrichtung, Livebild, Joystick und separate Mecanum-Seitwärtstasten.

## Bedienung

1. **Einlernen:** Karte beginnen oder nach dem Einschalten automatisch
   in der gespeicherten Karte wiederfinden lassen. Joystick oder
   Richtungstasten gedrückt halten; kein Freigabedialog. Loslassen stoppt. WASD bewegt, Q/E dreht.
2. **Sperrzonen:** Rasterzellen anklicken oder Rechtecke ziehen. 10, 25, 50 oder
   100 cm Zellengröße wählen. Rote Zellen werden sofort gespeichert und sowohl
   bei der Wegplanung als auch beim manuellen Fahren berücksichtigt.
3. **Ziele:** Eine freie Stelle auf der Karte anklicken oder ein benanntes Ziel
   auswählen. Nav2 plant den Weg um Wände, Hindernisse und Sperrzonen herum.

Karte, SLAM-Posegraph, Sperrzonen, Favoriten und Prüfergebnisse bleiben auf dem Pi.
Automatische Kartensicherung alle 30 Sekunden und vor regulärem Herunterfahren.
Ein kompletter Sicherungsdownload ist direkt in der Oberfläche möglich.

## Aktueller Hardware-Prüfstand

Rad-Richtungen und LiDAR-Ausrichtung sind am Gerät geprüft. **Eine Bodenfahrt ist
noch nicht verifiziert.** Manuelle Steuerung steht für beaufsichtigte erste
Prüfungen mit niedrigem Tempo und kontinuierlicher manueller Fahrt bereit. Unter
„Fahrprüfung & Einstellungen“ erst tatsächlich durchgeführte Prüfungen bestätigen.
Der Zielmodus lässt sich erst nach allen vier Bodenprüfungen freigeben.

Es sind keine Absturzsensoren bestätigt. Treppen physisch absichern; digitale
Sperrzonen ersetzen das nicht. Nach Neustart bleiben die Motoren immer gestoppt.

## Entwicklung / Betrieb

Siehe [Installation, Sicherung und Wiederherstellung](navigation/README.md) und
[geprüfter Stand](navigation/VERIFICATION.md). Die früheren Dateien `app.py` und
`src/` bleiben zur Referenz erhalten. Die alte und neue Motorsteuerung dürfen
nicht gleichzeitig laufen.

Karten, Wohnungsdaten, Protokolle und Zugangsdaten werden nicht ins Repository
übertragen; dafür gibt es lokale Sicherungen und den Download in der Oberfläche.
