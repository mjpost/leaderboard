#!/bin/bash

LEADERBOARD=$HOME/leaderboard
DATAROOT=$HOME/leaderboard/data

"$LEADERBOARD"/scripts/download-all.pl
"$LEADERBOARD"/scripts/build-table.pl > "$LEADERBOARD"/leaderboard.js

if diff "$LEADERBOARD"/leaderboard.js "$DATAROOT"/leaderboard.js > /dev/null
then
	# leaderboard.js hasn't changed.
	exit 0
fi

stamp=$(date +"%F-%H-%M")
cat "$DATAROOT"/leaderboard.js | perl -pe 's/var data/var olddata/' > "$DATAROOT"/leaderboard.js.$stamp
ln -sf "$DATAROOT"/leaderboard.js.$stamp "$DATAROOT"/leaderboard-old.js
mv "$LEADERBOARD"/leaderboard.js "$DATAROOT"/leaderboard.js
