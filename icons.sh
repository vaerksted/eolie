#!/bin/bash
for i in 16 22 32 48 256 512; do
	inkscape -z -e data/icons/hicolor/$ix$i/apps/org.gnome.Eolie.png -w $i -h $i data/icons/hicolor/org.gnome.Eolie.svg
done
