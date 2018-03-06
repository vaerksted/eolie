#!/bin/bash

function generate_resource()
{
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<gresources>'
    echo '  <gresource prefix="/org/gnome/Eolie">'
    for file in data/*.html data/*.css data/*.js
    do
        echo -n '    <file compressed="true">'
        echo -n $(basename $file)
        echo '</file>'
    done
    for file in data/*.ui AboutDialog.ui
    do
        echo -n '     <file compressed="true" preprocess="xml-stripblanks">'
        echo -n $(basename $file)
        echo '</file>'
    done
    echo '  </gresource>'
    echo '</gresources>'
}

function generate_po()
{
    cd po
    git pull https://hosted.weblate.org/git/gnumdk/eolie
    >eolie.pot
    for file in ../data/org.gnome.Eolie.gschema.xml ../data/*.in ../data/*.ui ../eolie/*.py
    do
        xgettext --from-code=UTF-8 -j $file -o eolie.pot
    done
    >LINGUAS
    for po in *.po
    do
        msgmerge -N $po eolie.pot > /tmp/$$language_new.po
        mv /tmp/$$language_new.po $po
        language=${po%.po}
        echo $language >>LINGUAS
    done
}

generate_resource > data/eolie.gresource.xml
generate_po
