import os
import sys
import time
import math
import urllib

from collections import defaultdict, namedtuple
import datetime

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

import scoring.upload_number
import scoring.alignment
import scoring.decode

#################################################################
# Assignment-related variables
#################################################################

scorer = [
  scoring.upload_number,
  scoring.alignment,
  scoring.decode
]

# The index of the current assignment (0-indexed)
CURRENT_ASSIGNMENT = len(scorer)-1

# Assignment deadlines in UTC and sore order (True = highest first)
reverse_order = [s.reverse_order for s in scorer]
DEADLINES = [s.deadline for s in scorer]
DEADLINES_PASSED = [datetime.datetime.now() >= x for x in DEADLINES]
default_score = [float("-inf") if x else float("inf") for x in reverse_order]

#################################################################
# End 
#################################################################

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(
    os.path.join(os.path.dirname(__file__), 'templates')),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

class Assignment(ndb.Model):
  """A database entry corresponding to an assignment."""
  user = ndb.UserProperty()
  number = ndb.IntegerProperty()
  filename = ndb.StringProperty()
  filedata = ndb.BlobProperty()
  score = ndb.FloatProperty()
  test_score = ndb.FloatProperty()
  percent_complete = ndb.IntegerProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True)


class Handle(ndb.Model):
  """A database entry recording a user's anonymizing handle."""
  user = ndb.UserProperty()
  leaderboard = ndb.BooleanProperty()
  handle = ndb.TextProperty()


# Clean up old assignments if they never got scored
TIMEOUT_MINUTES = 10
def fail_if_old(assignment, number):
  if assignment.score == default_score[number]:
    earliest_time = datetime.datetime.now() - datetime.timedelta(minutes=TIMEOUT_MINUTES)
    if assignment.timestamp < earliest_time:
      if assignment.percent_complete != 100:
        assignment.percent_complete = 100
        assignment.score = default_score[number]
        assignment.test_score = default_score[number]
        assignment.put()


def get_submission_history(user, i):
  return Assignment.query(Assignment.user == user,
                          Assignment.number == i).order(-Assignment.timestamp).fetch()


def most_recent_scored_submission(submission_history, user, i):
  return next((a for a in submission_history if a.percent_complete == 100 or a.percent_complete is None),
              submission_history[0] if len(submission_history) > 0 else
              Assignment(user=user, number=i, filedata=None, 
                         score=default_score[i], percent_complete=100))


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

    # Retrieve all the user's assignments. For each assignment, choose
    # the most recent submission that is 100% complete. For the most
    # recent assignment, collect its upload history
    assignments = []
    history = []
    progress = [] # ... of the assignment currently uploading
    for i, _ in enumerate(scorer):
      history.append(get_submission_history(user, i))
      for assignment in history[-1]:
        fail_if_old(assignment, i)
      assignments.append(most_recent_scored_submission(history[-1], user, i))
      progress.append(history[-1][0].percent_complete if len(history[-1]) > 0 else 100)

    template_values = {
      'user': user.email(),
      'handle': user_handle.handle,
      'leaderboard': user_handle.leaderboard,
      'checked': 'checked' if user_handle.leaderboard else '',
      'logout': users.create_logout_url('/'),
      'assignments': assignments,
      'expired': DEADLINES_PASSED,
      'history': history,
      'current': CURRENT_ASSIGNMENT,
      'progress': progress,
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')   
    self.response.write(template.render(template_values))


class Progress(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user is None:
      self.response.write("0")
    number = int(self.request.get('i'))
    history = get_submission_history(user, number)
    progress = 100
    if len(history) > 0:
      progress = history[0].percent_complete 
    self.response.write(progress)
 

class Upload(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))
    number = int(self.request.get('number'))
    filedata = self.request.get('file')
    assignment = Assignment(user = user,
                            number = number,
                            score = default_score[number],
                            test_score = default_score[number],
                            percent_complete = 0,
                            filedata = filedata,
                            filename = self.request.POST.multi['file'].filename)
    key = assignment.put() # only  way to get a key without fudging one? -- alopez
    (score, percent_complete) = scorer[number].score(filedata, key)
    (test_score, _) = scorer[number].score(filedata, key, test=True)
    assignment.score = score
    assignment.test_score = test_score
    assignment.percent_complete = percent_complete
    assignment.put() 
    self.redirect('/?')


class QueuedScore(webapp2.RequestHandler):
  def post(self):
    number = int(self.request.get('number'))
    key = ndb.Key(urlsafe=self.request.get('key'))
    data = self.request.get('data')
    scorer[number].queued_score(data, key)
    

## This triggers a potentially large update, so I've disabled it -- alopez
#class Rescore(webapp2.RequestHandler):
#  """Trigger manual rescoring of assignments."""
#  def get(self):
#    user = users.get_current_user()
#    for a in Assignment.query().fetch():
#      if a.filedata:
#        old_score = a.score
#        a.score = scorer[a.number].score(a.filedata)
#        a.test_score = scorer[a.number].score(a.filedata, test=True)
#        a.put()
#    self.redirect('/?')


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


class UpdateSchema(webapp2.RequestHandler):
  '''admin function: update entities created before the schema was extended'''
  def get(self):
    if users.is_current_user_admin():
      count = 0
      for a in Assignment.query().fetch():
        if a.percent_complete is None:
          a.percent_complete = 100
          a.put()
          count += 1
      self.response.write('Updated %d assignments\n' % (count,))


class LeaderBoard(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    handles = {}
    hidden_users = []
    names = {}
    for handle in Handle.query().fetch():
      # Ignore leaderboard prefs for self and for admins
      if handle.leaderboard:
        handles[handle.user] = handle.handle
      elif user is not None and (handle.user.email() == user.email() or users.is_current_user_admin()):
        handles[handle.user] = handle.handle
        hidden_users.append(handle.handle)
      if users.is_current_user_admin():
        names[handle.handle] = handle.user.nickname()

    scores = defaultdict(list)
    for user, handle in handles.iteritems():
      for i, _ in enumerate(scorer):
        history = get_submission_history(user, i)
        for assignment in history:
          fail_if_old(assignment, i)
        scores[handle].append(most_recent_scored_submission(history, user, i).score)

    for i, s in enumerate(scorer):
      scores['oracle'].append(s.oracle() if s.oracle() else default_score[i])
        
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
      'hidden_users': hidden_users,
      'scores': scores,
      'names': names,
    }

    self.response.write(template.render(template_values))


application = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/upload', Upload),
  ('/handle', ChangeHandle),
  ('/leaderboard.js', LeaderBoard),
  ('/queued_score', QueuedScore),
  ('/progress', Progress),
  ('/update_schema', UpdateSchema),
#  ('/rescore', Rescore),
], debug=True)
