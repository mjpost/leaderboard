#!/bin/bash

cd $HOME/code/mt-class
./scripts/download-all.pl
./scripts/build-table.pl > leaderboard.js

diff leaderboard.js $HOME/public_html/mt-class/leaderboard.js > /dev/null
if [[ $? -eq 1 ]]; then
    stamp=$(date +"%F-%H-%M")
    cat $HOME/public_html/mt-class/leaderboard.js | perl -pe 's/var data/var olddata/' > $HOME/public_html/mt-class/leaderboard.js.$stamp
    ln -sf leaderboard.js.$stamp $HOME/public_html/mt-class/leaderboard-old.js
    mv leaderboard.js $HOME/public_html/mt-class/leaderboard.js
fi
