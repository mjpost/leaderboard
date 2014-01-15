#!/bin/bash

# cd $HOME/code/mt-class.github.com
# git pull | grep -v "Already up-to-date"

cd $HOME/code/mt-class
./scripts/download-all.pl
./scripts/build-table.pl > leaderboard.js

diff leaderboard.js $HOME/public_html/mt-class/leaderboard.js > /dev/null
if [[ $? -eq 1 ]]; then
#    echo "Updating leaderboard (http://mt-class.org/leaderboard.html)"
    stamp=$(date +"%F-%H-%M")
    cat $HOME/public_html/mt-class/leaderboard.js | perl -pe 's/var data/var olddata/' > $HOME/public_html/mt-class/leaderboard.js.$stamp
    ln -sf leaderboard.js.$stamp $HOME/public_html/mt-class/leaderboard-old.js
    mv leaderboard.js $HOME/public_html/mt-class/leaderboard.js
    # cd $HOME/code/mt-class.github.com
    # git add leaderboard.html
    # stamp=$(date +"%F-%H-%M")
    # git commit -m "automatic update ($stamp)"
    # git push
fi
