# MT Class Leaderboard app

This project implements the [JHU MT class](http://mt-class.org/jhu) leaderboard as a
Google App Engine application. There are a few hard-coded variables (related to which
assignment is active, how many there are, where links go), but it's pretty modular and
relatively small.

To use it:

1. Clone it:

    git clone git@github.com:mjpost/leaderboard

1. Check out [the developer documentation](https://developers.google.com/appengine/) and in
particular
[the Python tutorial](https://developers.google.com/appengine/docs/python/gettingstartedpython27/introduction)
for instructions on how to download the test environment

1. Test it, make changes, etc:

    dev_appserver.py leaderboard/

1. Change the application ID in `app.yaml` to point to the app you created at
[appspot.com](appspot.com). 

1. Upload it with

    appcfg.py --oauth2 update leaderboard/
    
1. You can then access it at APP_ID.appspot.com

