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

function generate_pot()
{
    echo '[encoding: UTF-8]'
    for file in data/*.xml data/*.in eolie/*.py
    do
        echo $file
    done
    for file in data/*.ui data/AboutDialog.ui.in
    do
        echo -n '[type: gettext/glade]'
        echo $file
    done
}

function generate_po()
{
    cd po
    intltool-update --pot
    mv -f untitled.pot eolie.pot
    while read po
    do
        intltool-update $po
    done < LINGUAS
    cd -
}

generate_resource > data/eolie.gresource.xml
generate_pot > po/POTFILES.in
generate_po
