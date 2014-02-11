import os
import sys
import time
import math
import urllib

from collections import defaultdict

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

import scoring.alignment

# The sort order for all assignments (True = highest first, False = highest first)
reverse_order = [True, False, True, True, True]

# The index of the current assignment (0-indexed)
CURRENT_ASSIGNMENT = 1

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(
    os.path.join(os.path.dirname(__file__), 'templates')),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

def key(user, id):
  """Creates the key used to store assignments. Each key is a concatenation of the userid and the
assignment number."""

  return '%s / %s' % (user.user_id(), id)

class Assignment(ndb.Model):
  """A database entry corresponding to an assignment."""

  user = ndb.UserProperty()
  number = ndb.IntegerProperty()
  filename = ndb.StringProperty()
  filedata = ndb.BlobProperty()
  score = ndb.FloatProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True)

class Handle(ndb.Model):
  """A database entry recording a user's anonymizing handle."""
  user = ndb.UserProperty()
  leaderboard = ndb.BooleanProperty()
  handle = ndb.TextProperty()

class MainPage(webapp2.RequestHandler):
  """Displays the main page."""

  def get(self):
    user = users.get_current_user()

    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))

    # Create the user's handle in the database if it does not exist
    user_handle = Handle.get_by_id(user.user_id())
    if user_handle is None:
      user_handle = Handle(id = user.user_id(), 
                           user = user, 
                           leaderboard = True, 
                           handle = user.nickname())
      user_handle.put()

    # Retrieve all the user's assignments, up to and including the current one. Entries that don't
    # exist are created.
    assignments = [None for x in range(CURRENT_ASSIGNMENT+1)]
    for ass in Assignment.query(Assignment.user == user).fetch():
      if ass.number < len(assignments):
        assignments[ass.number] = ass
    for i in range(len(assignments)):
      if assignments[i] is None:
        user = users.get_current_user()
        assignments[i] = Assignment(id=key(user, i))
        assignments[i].user = user
        assignments[i].number = i
        assignments[i].datafile = None
        assignments[i].score = float("-inf") if reverse_order[i] else float("inf")
        assignments[i].put()

    template_values = {
      'user': user.email(),
      'handle': user_handle.handle,
      'leaderboard': user_handle.leaderboard,
      'checked': 'checked' if user_handle.leaderboard else '',
      'logout': users.create_logout_url('/'),
      'assignments': assignments,
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')   
    self.response.write(template.render(template_values))

# Scoring functions.
# These functions must be implemented to score each assignment.

def score_sanity_check(filedata):
  """Homework 0 (setup)."""
  value = filedata.split('\n')[0]
  try:
    return ((float(value)-1.0) % 100) + 1
  except ValueError:
    return -1

def score_dummy(filename):
  return 1.0

scorers = {
  '0': score_sanity_check,
  '1': scoring.alignment.score,
  '2': score_dummy,
  '3': score_dummy,
  '4': score_dummy,
  '5': score_dummy,
}

class Upload(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))

    number = self.request.get('number')
    assignment = Assignment.get_by_id(key(user, number))

    if assignment is None:
      print >> sys.stderr, "FATAL!"

    assignment.filedata = self.request.get('file')
    assignment.filename = self.request.POST.multi['file'].filename
    assignment.score = scorers.get(number)(assignment.filedata)
    assignment.put()

    self.redirect('/?')

class ChangeHandle(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))

    user_handle = Handle.get_by_id(user.user_id())
    user_handle.handle = self.request.get('handle')
    user_handle.leaderboard = (self.request.get('leaderboard') == 'True')
    user_handle.put()

    self.redirect('/?')

class LeaderBoard(webapp2.RequestHandler):
  def get(self):
    handles = {}
    for handle in Handle.query().fetch():
      if handle.leaderboard:
        handles[handle.user] = handle.handle

    def default_score(x):
      return float('-inf') if reverse_order[x] else float('inf')

    scores = defaultdict(list)
    for a in Assignment.query().fetch():
      if handles.has_key(a.user):
        user_handle = handles[a.user]
        if not scores.has_key(user_handle):
          scores[user_handle] = [default_score(x) for x in range(CURRENT_ASSIGNMENT+1)]

        if a.number <= CURRENT_ASSIGNMENT:
          if math.isnan(a.score):
            scores[user_handle][a.number] = float('-inf') if reverse_order[CURRENT_ASSIGNMENT] else float('inf')
          else:
            scores[user_handle][a.number] = a.score

    def score_sort(x, y):
      index = CURRENT_ASSIGNMENT
      while index >= 0:
        which = cmp(scores[x][index], scores[y][index])
        if which != 0:
          return which
        index -= 1
      return 0

    sorted_handles = sorted(scores.keys(), cmp=score_sort, reverse=reverse_order[CURRENT_ASSIGNMENT])

    template = JINJA_ENVIRONMENT.get_template('leaderboard.js')
    template_values = {
      'handles': sorted_handles,
      'scores': scores,
    }

    self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/upload', Upload),
  ('/handle', ChangeHandle),
  ('/leaderboard.js', LeaderBoard),
], debug=True)
